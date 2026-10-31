"""Find it by sound: "Hey Andy, I'm ringing my phone."

A phone under a cushion is invisible to a camera, but it can ring, and a tracker on a key ring can chirp. The robot's
microphone array says which side a sound comes from (Pollen's DoA; robot/reachy_mini.py listen), so Andy turns its
head towards the ringing until the array hears it straight ahead, the way a person turns to a sound, then looks with
SAM 3.1 only around that way. If it still can't see it, it points where the sound is: "I can hear it, but I can't
see it. It's ringing over there."

Why turn rather than read the angle once: on the robot (2026-10-31, evals/sound.py) the array's angle followed a
fixed ringtone by only 0.2 to 0.45 degrees for each degree the head turned. One reading says which side, reliably,
but not how far; where the array hears the sound straight ahead is where the sound is.

What counts as ringing: chunks (about 0.1 s each) much louder than the room's own noise, most of them tonal, as a
ringtone or a chirp is and a voice isn't (spectral flatness: a pure tone near 0, noise near 1; measured on the robot,
the loud chunks of two ringtones 0.000 to 0.008, of a spoken sentence 0.004 to 0.18, median 0.03 to 0.06), and with
a direction from the array. Nothing is recorded: per chunk only its loudness, its flatness and its direction are kept,
for 20 seconds.
"""
import math
import time
from collections import deque

import numpy as np

RATE = 16000
TONAL = 0.015  # spectral flatness at or below this is a tone
TONAL_SHARE = 0.6  # of the loud chunks, at least this many must be tones: a voice is tonal only now and then
LOUDER = 4.0  # times the room's noise floor
QUIET_FLOOR = 0.004  # a floor for very quiet rooms, so a click isn't "four times louder"
ENOUGH = 4  # ringing chunks with a side for one reading (a reading listens about 1.6 s: two rings or more)
AHEAD_DEG = 1.0  # a reading this small is straight ahead
STEP_DEG = 40.0  # a turn towards the side heard, until the sound is between two turns
NARROW_DEG = 10.0  # then halve the gap, by which side each reading puts the sound, until it's this narrow
TURNS = 7  # at most


def flatness(samples: np.ndarray, rate: int = RATE) -> float:
    """Spectral flatness over 300 Hz to 5 kHz: the geometric over the arithmetic mean of the power. 0: a pure tone."""
    x = np.asarray(samples, dtype=np.float64)
    if len(x) < 64:
        return 1.0
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / rate)
    band = p[(f >= 300) & (f <= 5000)] + 1e-12
    return float(np.exp(np.mean(np.log(band))) / np.mean(band))


class Ear:
    """The last few seconds the microphones heard, as numbers: (when, loudness, flatness, side) per chunk, where side
    is how many degrees left of where the head looks the array put the sound (compressed, so a side more than an
    angle), or None. The voice loop fills it as it listens (voice/loop.py run); a turn reads it."""

    def __init__(self, head=lambda: 0.0, seconds: float = 20.0, clock=time.monotonic):
        self.head, self.clock, self.seconds = head, clock, seconds
        self._chunks: deque = deque()

    def __call__(self, samples, flag: bool, yaw: float | None) -> None:
        x = np.asarray(samples, dtype=np.float32)
        now = self.clock()
        side = (yaw - self.head()) if flag and yaw is not None else None
        self._chunks.append((now, float(np.sqrt(np.mean(x * x))) if len(x) else 0.0, flatness(x), side))
        while self._chunks and now - self._chunks[0][0] > self.seconds:
            self._chunks.popleft()

    def since(self, t: float) -> list[tuple]:
        return [c for c in list(self._chunks) if c[0] >= t]

    def floor(self) -> float:
        """The room's own noise: a low percentile of everything heard lately."""
        levels = sorted(c[1] for c in self._chunks)
        return max(levels[len(levels) // 5] if levels else 0.0, QUIET_FLOOR)


def ringing(chunks: list[tuple], floor: float) -> list[tuple]:
    """The chunks that are a ringing: loud, tonal (most of the loud ones must be), with a side. [] if it isn't one."""
    loud = [c for c in chunks if c[1] >= LOUDER * max(floor, QUIET_FLOOR)]
    tones = [c for c in loud if c[2] <= TONAL]
    if not loud or len(tones) < TONAL_SHARE * len(loud):
        return []
    with_side = [c for c in tones if c[3] is not None]
    return with_side if len(with_side) >= ENOUGH else []


def reading(chunks: list[tuple], floor: float) -> float | None:
    """Which side of the head the ringing is on, in the array's (compressed) degrees: positive left. None: no ringing."""
    r = ringing(chunks, floor)
    return float(np.median([c[3] for c in r])) if r else None


def turn_to(listen, turn, start: float, reach=(-150.0, 150.0), on_step=None) -> tuple[float | None, list]:
    """Turn the head towards a ringing: by the side only, since the array's angle is too compressed to trust for how
    far (see above). listen() -> a reading at the head's current yaw (None: no ringing); turn(yaw) moves the head.
    STEP_DEG towards the side heard until the sound is between two yaws, then halve the gap until it's NARROW_DEG.
    Returns (the yaw facing it, or None if nothing was heard; the steps [(yaw, reading)])."""
    steps, yaw, left, right = [], start, None, None  # left/right: yaws with the sound on that side of the head
    for _ in range(TURNS):
        turn(yaw)
        side = listen()
        if side is None:
            side = listen()  # a gap between rings: once more
            if side is None:
                break
        steps.append((yaw, side))
        if on_step:
            on_step(yaw, side, steps)
        if abs(side) <= AHEAD_DEG:
            return yaw, steps
        if side > 0:
            right = yaw if right is None else max(right, yaw)  # the sound is left of here: it's at a larger yaw
        else:
            left = yaw if left is None else min(left, yaw)
        if right is not None and left is not None:
            if left - right <= NARROW_DEG:
                return (left + right) / 2, steps
            nxt = (left + right) / 2
        else:
            nxt = yaw + math.copysign(STEP_DEG, side)
        nxt = min(max(nxt, reach[0]), reach[1])
        if abs(nxt - yaw) < 1.0:
            break
        yaw = nxt
    if not steps:
        return None, steps
    if right is not None and left is not None:
        return (left + right) / 2, steps
    return min(steps, key=lambda s: abs(s[1]))[0], steps


def apart(a: float, b: float) -> float:
    """Degrees between two yaws, the short way round."""
    return abs((a - b + 180) % 360 - 180)


def fan(yaw: float) -> tuple:
    """Where to look for a thing heard at this yaw: that way first, low and high, then a little either side."""
    return ((yaw, 20.0), (yaw, 35.0), (yaw + 22.0, 25.0), (yaw - 22.0, 25.0), (yaw, 8.0))
