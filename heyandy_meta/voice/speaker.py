"""Andy's voice: each sentence is made on this computer and played as soon as it's ready."""
import re
import time

SENTENCE = re.compile(r"(?<=[.!?])\s+")


class Speaker:
    def __init__(self, voice, play, rate: int = 16000):
        self.voice, self.play, self.rate = voice, play, rate
        self.started: list[float] = []  # time.monotonic() when each recent thing said started playing

    def __call__(self, text: str) -> None:
        first = True
        for sentence in SENTENCE.split(text.strip()):
            if sentence.strip():
                audio = self.voice.speak(sentence, rate=self.rate)
                if first:
                    self.started, first = (self.started + [time.monotonic()])[-8:], False
                self.play(audio, self.rate)

    def first_after(self, t: float) -> float | None:
        """When Andy first made a sound after time t (e.g. the end of what the person said)."""
        return next((s for s in self.started if s >= t), None)
