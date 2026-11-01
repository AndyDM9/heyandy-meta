"""Andy's voice: each sentence is made on this computer and played as soon as it's ready."""
import queue
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
        self._later: queue.Queue = queue.Queue()  # said soon: in order, by one worker, never over each other
        self._worker: threading.Thread | None = None

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
        self._later.join()  # whatever was to be said soon comes first
        with self._turn:
            self._say(text)

    def wait(self) -> None:
        """Until everything to be said soon has been said (a sound of Andy's own mustn't play over it)."""
        self._later.join()

    def soon(self, text: str) -> None:
        """Say it without waiting ("Let me look." while the head starts turning), even while something else is being said:
        it's queued, and said in order; whatever is said next, with or without waiting, comes after it. (It once waited
        while the first turn's "I'm Andy, an AI robot." played, and held up the search 2.4 s.)"""
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._saying, daemon=True, name="saying")
            self._worker.start()
        self._later.put(text)

    def _saying(self) -> None:
        while True:
            text = self._later.get()
            try:
                with self._turn:
                    self._say(text)
            except Exception:  # noqa: BLE001 - a sentence that can't be made or played mustn't stop the next
                pass
            finally:
                self._later.task_done()

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
