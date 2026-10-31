"""Andy's voice: each sentence is made on this computer and played as soon as it's ready."""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

SENTENCE = re.compile(r"(?<=[.!?])\s+")


class Speaker:
    def __init__(self, voice, play, rate: int = 16000):
        self.voice, self.play, self.rate = voice, play, rate
        self.started: list[float] = []  # time.monotonic() when each recent thing said started playing
        self._turn = threading.Lock()  # one thing said at a time, in order
        self._maker = ThreadPoolExecutor(1, thread_name_prefix="voice")  # the next sentence, made while one plays
        self._kept: dict[tuple, object] = {}  # short fixed phrases ("There it is!", "Let me look."), as they sound

    def _make(self, sentence: str):
        """A short phrase Andy says again and again is made once per voice setting; anything longer, every time."""
        if len(sentence.split()) > 4:
            return self.voice.speak(sentence, rate=self.rate)
        key = (sentence, getattr(self.voice, "voice", None), getattr(self.voice, "speed", None),
               getattr(self.voice, "loudness", None), self.rate)
        if key not in self._kept:
            if len(self._kept) >= 64:
                self._kept.pop(next(iter(self._kept)))
            self._kept[key] = self.voice.speak(sentence, rate=self.rate)
        return self._kept[key]

    def __call__(self, text: str) -> None:
        with self._turn:
            self._say(text)

    def soon(self, text: str) -> None:
        """Say it without waiting ("Let me look." while the head starts turning). The turn is taken now, so whatever
        is said next comes after it."""
        self._turn.acquire()

        def run():
            try:
                self._say(text)
            finally:
                self._turn.release()

        threading.Thread(target=run, daemon=True, name="saying").start()

    def _say(self, text: str) -> None:
        sentences = [x for x in SENTENCE.split(text.strip()) if x.strip()]
        coming = self._maker.submit(self._make, sentences[0]) if sentences else None
        for i in range(len(sentences)):
            audio = coming.result()
            coming = self._maker.submit(self._make, sentences[i + 1]) if i + 1 < len(sentences) else None
            if i == 0:
                self.started = (self.started + [time.monotonic()])[-8:]
            self.play(audio, self.rate)

    def first_after(self, t: float) -> float | None:
        """When Andy first made a sound after time t (e.g. the end of what the person said)."""
        return next((s for s in self.started if s >= t), None)
