"""Cutting the microphone stream into utterances: speech starts, then ends after a short silence.

Speech is the microphone array's own voice detector or, failing that, sound well above the room's noise floor, which
is learned while it's quiet. A little audio from before the start is kept so the first word isn't clipped.
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Endpointer:
    rate: int = 16000
    ratio: float = 2.5  # this many times the noise floor counts as speech
    min_speech_s: float = 0.25
    end_silence_s: float = 0.55
    max_s: float = 8.0  # a request is a sentence or two; longer means the room never went quiet
    pre_roll_s: float = 0.3
    floor: float = 0.01
    floor_window_s: float = 4.0  # nothing quiet for this long: the room is louder than the floor says
    _buf: list = field(default_factory=list)
    _pre: list = field(default_factory=list)
    _speech_s: float = 0.0
    _silence_s: float = 0.0
    _len_s: float = 0.0
    _recent: deque = field(default_factory=deque)
    _recent_s: float = 0.0

    def _relearn(self, rms: float, dur: float) -> None:
        """The floor was learned only while quiet, so it could fall but never climb: a moment of near-silence from the
        array took it to 0.001, after which the room's own noise counted as speech, nothing was ever quiet again, and
        every stretch ran to max_s with "Hey Andy" buried in it (November 3 and 4; it looked like failing microphones,
        and each restart of Andy seemed to cure it). So the quietest moment of the last few seconds is the room: speech
        has gaps between its words, and a room that never drops below the floor is louder than the floor says."""
        if not dur:
            return
        self._recent.append((rms, dur))
        self._recent_s += dur
        while self._recent_s - self._recent[0][1] >= self.floor_window_s:
            self._recent_s -= self._recent.popleft()[1]
        if self._recent_s >= self.floor_window_s:
            quietest = min(r for r, _ in self._recent)
            if quietest > self.floor * 1.5:
                self.floor = quietest

    @property
    def active(self) -> bool:
        """Someone is speaking right now (an utterance has started and not yet ended)."""
        return bool(self._buf)

    def feed(self, chunk: np.ndarray, speech_flag: bool | None = None) -> np.ndarray | None:
        """Add mono samples; returns a finished utterance, or None."""
        chunk = np.asarray(chunk, dtype=np.float32)
        dur = len(chunk) / self.rate
        rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0
        self._relearn(rms, dur)
        loud = rms > self.floor * self.ratio
        # The microphone's own detector can stay on with motor hum or a TV; it counts only with some sound behind it.
        speech = loud or (bool(speech_flag) and rms > self.floor * 1.5)
        if not self._buf:
            if not speech:
                self.floor = 0.95 * self.floor + 0.05 * max(rms, 1e-4)  # learn the room while quiet
                self._pre = (self._pre + [chunk])[-max(1, int(self.pre_roll_s / max(dur, 1e-3))):]
                return None
            self._buf, self._pre = self._pre + [chunk], []
            self._speech_s, self._silence_s, self._len_s = dur, 0.0, dur
            return None
        self._buf.append(chunk)
        self._len_s += dur
        if speech:
            self._speech_s += dur
            self._silence_s = 0.0
        else:
            self._silence_s += dur
        if self._silence_s >= self.end_silence_s or self._len_s >= self.max_s:
            out, enough = np.concatenate(self._buf), self._speech_s >= self.min_speech_s
            self._buf, self._speech_s, self._silence_s, self._len_s = [], 0.0, 0.0, 0.0
            return out if enough else None
        return None
