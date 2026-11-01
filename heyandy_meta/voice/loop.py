"""The spoken conversation: Andy answers when called by name, then keeps listening for a short while.

Only speech that starts with "Hey Andy" (or plain "Andy", unless Andy was asked to answer only to "Hey Andy") is answered; after an answer, follow-ups need no name for
``follow_up_s``. When called, Andy turns towards the voice first, using the microphone array's direction. While it
speaks, the microphone is ignored so it doesn't answer itself.
"""
import logging
import queue
import re
import threading
import time

from ..companion.safety import crisis

log = logging.getLogger(__name__)

# "Andy" as speech-to-text writes it: the name, and what it was heard as on 2026-10-27 ("and they", "earndy").
NAME = r"(?:andy|andi|andí|andie|andee|endy|earndy|handy|annie)"
WAKE = re.compile(r"^\W*(?:(?:hey|hi|hello|ok|okay|oye|hola)\s+)?(?:" + NAME + r"|and he|and they)\b[\s,.!?]*", re.I)
# The name later on, when the room ran the words together ("... so anyway. Andy, how are you"): what follows it.
LATER = re.compile(r"\b(?:(?:hey|hi|hello|ok|okay|oye|hola)\s+)?" + NAME + r"\b[\s,.!?]*(?=\S)", re.I)
# "Answer only to 'Hey Andy'" (a home with someone called Andy): the greeting is needed, plain "Andy" is a person
HEY = r"(?:hey|hi|hello|ok|okay|oye|hola)\s+"
HEY_WAKE = re.compile(r"^\W*" + HEY + r"(?:" + NAME + r"|and he|and they)\b[\s,.!?]*", re.I)
HEY_LATER = re.compile(r"\b" + HEY + NAME + r"\b[\s,.!?]*(?=\S)", re.I)


class VoiceLoop:
    def __init__(self, andy, follow_up_s: float = 20.0, clock=time.monotonic, on_heard=None):
        self.andy, self.follow_up_s, self._clock, self.on_heard = andy, follow_up_s, clock, on_heard
        self.awake_until = float("-inf")
        self.utterance_end = 0.0  # time.monotonic() when the last utterance ended
        self.busy = False  # a turn is running (on its own thread, so "stop" and "done" can still be heard)
        self._pending = None  # crisis words heard during a turn: answered straight after it

    def stops(self, text: str) -> bool:
        """Words that end what Andy is doing right now: "stop" a follow, "done" shuffling the cups."""
        return getattr(self.andy, "following", False) and bool(
            STOP.search(text) or (getattr(self.andy, "playing", False) and DONE.search(text)))

    def heard(self, text: str, voice_yaw: float | None = None) -> str | None:
        """One utterance's text. Returns what Andy said, or None if it wasn't for Andy."""
        text = " ".join(text.split())
        if crisis(text) and not self.stops(text) and getattr(self.andy, "following", False):
            self.andy.stop_following()  # whatever Andy is doing, this comes first
        if self.stops(text) and not crisis(text):
            self.andy.stop_following()  # no lock: the follow holds it, and this must reach it at once
            return "Stopped."
        if _looping(text):
            return None  # speech-to-text going round in circles on noise ("the state of the state of ...")
        if getattr(self.andy, "hey_only", False):  # only "Hey Andy" (or "Oye Andy"): plain "Andy" may be a person
            called = HEY_WAKE.match(text) or next(reversed(list(HEY_LATER.finditer(text))), None)
        else:
            called = WAKE.match(text) or _soft_wake(text) or next(reversed(list(LATER.finditer(text))), None)
        if not text or (not called and self._clock() > self.awake_until):
            return None  # not for Andy: dropped, never shown or kept
        rest = text[called.end():] if called else text
        if crisis(text):
            rest = text  # "I want to die. Andy, what time is it": the whole of it, so nothing is missed
        chime = getattr(self.andy, "chime", None)
        if called and chime and not crisis(text):
            chime("heard")  # at once, before any words: Andy heard its name (never for crisis words)
        with getattr(self.andy, "lock", _NoLock()):
            if voice_yaw is not None:  # the voice gives the direction; keep the last seen face's height
                before = getattr(self.andy, "person", None)
                self.andy.person = (voice_yaw, before[1] if before else -5.0)
            if called and voice_yaw is not None:  # turn towards whoever spoke, while the answer is being made
                self.andy.turn_to_person(voice_yaw)
            if called and hasattr(self.andy.body, "gesture"):
                self.andy.body.gesture("listening")
            if rest.strip(" ,.!?"):
                reply = self.andy.hear(rest)
                screen = getattr(self.andy, "screen", None)
                if screen:
                    screen.used("Omnilingual ASR (hearing)", "device")
                    screen.used("SeamlessM4T v2 (voice)", "device")
            else:
                reply = "Yes?"
                self.andy.say(reply)
        self.awake_until = self._clock() + self.follow_up_s
        return reply

    def run(self, mic, voice, endpointer, stop) -> None:
        """Listen until ``stop`` is set: mic yields (samples, speech_flag, voice_yaw); quiet while Andy speaks.

        Turns run on a thread of their own, so listening never pauses: "stop" reaches a follow and "done" reaches the
        cup game while they run. Anything else said during a turn is dropped, as it was before (unheard)."""
        gesture = getattr(self.andy.body, "gesture", None)
        hearing = False
        turns: queue.Queue = queue.Queue(maxsize=1)
        threading.Thread(target=self._turns, args=(turns, endpointer, stop), daemon=True).start()
        ear = getattr(self.andy, "ear", None)
        for samples, flag, yaw in mic(stop):
            if ear is not None:
                ear(samples, flag, yaw)  # loudness, tone and direction only, for "I'm ringing my phone" (companion/sound.py)
            utterance = endpointer.feed(samples, flag)
            if gesture and not self.busy and endpointer.active != hearing and self._clock() <= self.awake_until:
                hearing = endpointer.active
                gesture("listening" if hearing else "idle")  # attentive while a follow-up is spoken
                screen = getattr(self.andy, "screen", None)
                if screen and hearing:
                    screen.doing("Listening", "Looking at you")
            if utterance is None:
                continue
            self.utterance_end = time.monotonic() - endpointer.end_silence_s
            try:
                voice.language = getattr(self.andy, "asr_language", "eng_Latn")  # what Omnilingual ASR will hear
                asr_started = time.monotonic()
                text = voice.transcribe(utterance)
                hood = getattr(self.andy, "hood", None)
                if hood is not None:  # under the hood: the words ended then, and hearing them took this long
                    hood.heard(self.utterance_end, time.monotonic() - asr_started)
            except Exception as e:  # noqa: BLE001 - one bad utterance must not leave Andy deaf
                log.warning("hearing failed: %s: %s", type(e).__name__, e)
                continue
            if self.busy:
                if crisis(text):  # never dropped: stop what's running, and answer it as soon as the turn ends
                    self.andy.stop_following()
                    self._pending = (text, yaw, utterance)
                    continue
                stopped = self.stops(text)
                if stopped:
                    self.andy.stop_following()  # no lock: the turn holds it, and this must reach it at once
                self._report(None, "Stopped." if stopped else None, utterance, endpointer)  # its length only
                continue
            self.busy = True
            turns.put((text, yaw, utterance))

    def _turns(self, turns: queue.Queue, endpointer, stop) -> None:
        while not stop.is_set():
            try:
                text, yaw, utterance = turns.get(timeout=0.5)
            except queue.Empty:
                continue
            reply = None
            try:
                reply = self.heard(text, yaw)
            except Exception as e:  # noqa: BLE001 - one bad turn must not leave Andy deaf
                log.warning("a turn failed: %s: %s", type(e).__name__, e)
            finally:
                pending, self._pending = self._pending, None
                if pending:  # crisis words said during that turn: answered now, before anything else
                    turns.put(pending)
                else:
                    self.busy = False
            self._report(text if reply is not None else None, reply, utterance, endpointer)

    def _report(self, text, reply, utterance, endpointer) -> None:
        if self.on_heard:  # what wasn't for Andy is reported by its length only, never its words
            self.on_heard(text if text is not None else
                          f"{len(utterance) / endpointer.rate:.1f}s of speech, room level {endpointer.floor:.3f}", reply)


def _looping(text: str) -> bool:
    words = text.lower().split()
    if len(words) < 12:
        return False
    grams = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    return max(grams.count(g) for g in set(grams)) >= 4 or len(set(words)) / len(words) < 0.35


STOP = re.compile(r"\b(?:stop|enough|that's enough|okay thanks|thank you|basta|detente|ya basta)\b|^\W*(?:para|alto)\W*$",
                  re.I)  # "para" and "alto" only alone: "es para mi hija", "habla más alto"
DONE = re.compile(r"\b(?:done|ready|finished|where(?:'s| is) (?:it|the ball)|which (?:one|cup)|your turn|go ahead|"
                  r"listo|lista|ya está|terminé|cuál|dónde está)\b",
                  re.I)  # the cup game: the shuffle is over
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
