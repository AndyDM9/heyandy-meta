"""The spoken conversation: Andy answers when called by name, then keeps listening for a short while.

Only speech that starts with "Andy" (or "hey Andy") is answered; after an answer, follow-ups need no name for
``follow_up_s``. When called, Andy turns towards the voice first, using the microphone array's direction. While it
speaks, the microphone is ignored so it doesn't answer itself.
"""
import re
import time

# "Andy" as speech-to-text writes it: the name, and what it was heard as on 2026-10-27 ("and they", "earndy").
WAKE = re.compile(r"^\W*(?:(?:hey|hi|hello|ok|okay)\s+)?"
                  r"(?:andy|andi|andie|andee|endy|earndy|handy|annie|and he|and they)\b[\s,.!?]*", re.I)


class VoiceLoop:
    def __init__(self, andy, follow_up_s: float = 20.0, clock=time.monotonic, on_heard=None):
        self.andy, self.follow_up_s, self._clock, self.on_heard = andy, follow_up_s, clock, on_heard
        self.awake_until = float("-inf")
        self.utterance_end = 0.0  # time.monotonic() when the last utterance ended

    def heard(self, text: str, voice_yaw: float | None = None) -> str | None:
        """One utterance's text. Returns what Andy said, or None if it wasn't for Andy."""
        text = " ".join(text.split())
        if _looping(text):
            return None  # speech-to-text going round in circles on noise ("the state of the state of ...")
        called = WAKE.match(text) or _soft_wake(text)
        if not text or (not called and self._clock() > self.awake_until):
            return None  # not for Andy: dropped, never shown or kept
        rest = text[called.end():] if called else text
        with getattr(self.andy, "lock", _NoLock()):
            if called and voice_yaw is not None:
                self.andy.body.look(voice_yaw, 5.0, precise=False)  # turn towards whoever spoke
            if called and hasattr(self.andy.body, "gesture"):
                self.andy.body.gesture("listening")
            if rest.strip(" ,.!?"):
                reply = self.andy.hear(rest)
                screen = getattr(self.andy, "screen", None)
                if screen:
                    screen.used("Omnilingual ASR (hearing)", "device")
                    screen.used("Kokoro (voice)", "device")
            else:
                reply = "Yes?"
                self.andy.say(reply)
        self.awake_until = self._clock() + self.follow_up_s
        return reply

    def run(self, mic, voice, endpointer, stop) -> None:
        """Listen until ``stop`` is set: mic yields (samples, speech_flag, voice_yaw); quiet while Andy speaks."""
        for samples, flag, yaw in mic(stop):
            utterance = endpointer.feed(samples, flag)
            if utterance is not None:
                self.utterance_end = time.monotonic() - endpointer.end_silence_s
                text = voice.transcribe(utterance)
                reply = self.heard(text, yaw)
                if reply is not None and self.on_heard:  # only what was for Andy
                    self.on_heard(text, reply)


def _looping(text: str) -> bool:
    words = text.lower().split()
    if len(words) < 12:
        return False
    grams = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    return max(grams.count(g) for g in set(grams)) >= 4 or len(set(words)) / len(words) < 0.35


SOFT = re.compile(r"^\W*and\b[\s,]*", re.I)


def _soft_wake(text: str):
    """"Andy" is often heard as "and": count it only when what follows is a clear request, not chat."""
    from ..companion.intents import parse

    m = SOFT.match(text)
    return m if m and parse(text[m.end():]).kind not in ("chat", "world") else None


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
