"""Andy's voice: each sentence is made on this computer and played as soon as it's ready."""
import re
import time

SENTENCE = re.compile(r"(?<=[.!?])\s+")


class Speaker:
    def __init__(self, voice, play, rate: int = 16000):
        self.voice, self.play, self.rate = voice, play, rate
        self.first_sound = 0.0  # time.monotonic() when the last thing said started playing

    def __call__(self, text: str) -> None:
        first = True
        for sentence in SENTENCE.split(text.strip()):
            if sentence.strip():
                audio = self.voice.speak(sentence, rate=self.rate)
                if first:
                    self.first_sound, first = time.monotonic(), False
                self.play(audio, self.rate)
