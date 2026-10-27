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
        called = WAKE.match(text)
        if not text or (not called and self._clock() > self.awake_until):
            return None
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
                if self.on_heard:
                    self.on_heard(text, reply)


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
