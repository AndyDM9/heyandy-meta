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

import numpy as np

from ..companion.safety import crisis, emergency, unasked_urgent

log = logging.getLogger(__name__)

# "Andy" as speech-to-text writes it: the name, and what it was heard as on 2026-10-27 ("and they", "earndy").
NAME = r"(?:andy|andi|andí|andie|andee|endy|earndy|handy|annie)"
# and as Andy's other languages write it (Chinese and Korean run straight on into the next word: no word boundary)
NATIVE = r"(?:安迪|安蒂|앤디|엔디|энди|енді|енди|آندي|أندي|اندي|एंडी|ऐंडी)"
CALL = r"(?:(?:" + NAME + r"|and he|and they)\b|" + NATIVE + r")"
PAUSE = r"[\s,.!?，、。！？]*"
WAKE = re.compile(r"^\W*(?:(?:hey|hi|hello|ok|okay|oye|hola)\s+)?" + CALL + PAUSE, re.I)
# "Hey Andy" as speech-to-text also writes it: "hey and how are you", "hey any where are my glasses" (November 4: short
# sentences at a good level, nearest word "and"). Alone "and" is everyday speech, but nobody starts a sentence "hey and".
HEY_HEARD = re.compile(r"^\W*hey[\s,]+(\w+)\b" + PAUSE, re.I)
HEARD_AS = {"end", "engine", "enji", "angie", "angel", "endim"}  # November 4, the founder's takes: not spelled alike, but it was the name
HEARD_ALIKE = 0.66  # "wendy" 0.67, "indy" 0.75, "and" and "any" 0.86, "sandy" 0.89; "andrew" 0.6 and "buddy" 0.44 aren't


def _hey_heard(text: str):
    """"Hey" and then a word near enough to Andy's name, at the very start: a call, whatever the recogniser wrote."""
    from difflib import SequenceMatcher

    m = HEY_HEARD.match(text)
    if not m:
        return None
    word = m.group(1).lower()
    return m if word in HEARD_AS or SequenceMatcher(None, word, "andy").ratio() >= HEARD_ALIKE else None


# The name later on, when the room ran the words together ("... so anyway. Andy, how are you"): what follows it.
LATER = re.compile(r"(?:\b(?:(?:hey|hi|hello|ok|okay|oye|hola)\s+)?" + NAME + r"\b|" + NATIVE + r")" + PAUSE + r"(?=\S)", re.I)
# "Answer only to 'Hey Andy'" (a home with someone called Andy): the greeting is needed, plain "Andy" is a person
HEY = r"(?:hey|hi|hello|ok|okay|oye|hola)\s+"
HEY_WAKE = re.compile(r"^\W*" + HEY + r"(?:" + NAME + r"|and he|and they)\b[\s,.!?]*", re.I)
HEY_LATER = re.compile(r"\b" + HEY + NAME + r"\b[\s,.!?]*(?=\S)", re.I)

# After a reply Andy takes what's said next without its name, as a person would. Each reply opens that window again, so
# a room's own talk could keep it answering: November 2, in a meeting near the robot, 26 turns in 20 minutes, each
# within 20 s of the last, until the robot was unplugged (research.md section 79). So:
FOLLOW_UPS = 6  # at most this many in a row without the name, then the name again: a backstop for a room that waits
FAINT_LEVEL = 0.01  # a sound's own loudness (RMS) below which, without the name, it isn't speech for Andy


NOISE_PEAK = 0.05  # a sound that never gets this loud isn't a voice: a voice peaks at 0.15 to 1, the room's noises at 0.01 to 0.04


def _noise(utterance) -> bool:
    """A stretch with nothing in it as loud as a voice. Given near-silence, speech-to-text writes words anyway (November
    4: 62 of them from 8 s of quiet): they kept GPU 1 at 94%, held up hearing while they were written, and counted as
    the room talking, which closed the follow-ups after every answer. So these never reach it."""
    x = np.asarray(utterance, dtype=np.float32)
    return not len(x) or float(np.abs(x).max()) < NOISE_PEAK


def _loudness(utterance) -> float | None:
    """An utterance's own loudness (RMS), the number the journal reports; None when there are no samples."""
    x = np.asarray(utterance, dtype=np.float32)
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else None
                # for Andy to finish (the meeting's own talk over its answers is what ends a chain: below)
# and when the room is talking (people, a call on speaker, the TV), this many utterances Andy wasn't called in, or said
# over its own answer, within this long: a conversation it isn't part of, so it answers its name and takes nothing
# after, unless it asked something (one answer, then the name again)
ROOM_TALKING = (5, 90.0)




class VoiceLoop:
    def __init__(self, andy, follow_up_s: float = 20.0, clock=time.monotonic, on_heard=None,
                 follow_ups: int = FOLLOW_UPS, room_talking: tuple[int, float] = ROOM_TALKING):
        self.andy, self.follow_up_s, self._clock, self.on_heard = andy, follow_up_s, clock, on_heard
        self.follow_ups, self.room_talking = follow_ups, room_talking
        self.awake_until = float("-inf")
        self.follow_ups_left = 0  # what Andy will still take without its name, until it's called again
        self._not_for_andy: list[float] = []  # when utterances it wasn't called in ended: only the times, never words
        self.utterance_end = 0.0  # time.monotonic() when the last utterance ended
        self.marks: dict = {}  # the turn's own times (time.monotonic()): heard, listened again, began; never words
        self._again: tuple[float, float] | None = None
        self.busy = False  # a turn is running (on its own thread, so "stop" and "done" can still be heard)
        self._pending = None  # crisis words heard during a turn: answered straight after it

    def listening(self) -> bool:
        """Andy takes what's said next without its name: just after a reply, and only so many times in a row."""
        return self._clock() <= self.awake_until and self.follow_ups_left > 0

    def _count(self, for_andy: bool) -> None:
        """One utterance heard, and whether it was for Andy: for "what did you hear today?" (a number, never words)."""
        screen = getattr(self.andy, "screen", None)
        if screen is not None and hasattr(screen, "heard_speech"):
            screen.heard_speech(for_andy)

    def not_for_andy(self) -> None:
        """An utterance Andy wasn't called in, or said over its answer: when it ended, never what it said."""
        self._not_for_andy.append(self._clock())

    def talking_room(self) -> bool:
        """A conversation in the room that isn't with Andy: enough utterances lately that it wasn't called in."""
        n, seconds = self.room_talking
        now = self._clock()
        self._not_for_andy = [t for t in self._not_for_andy if now - t <= seconds]
        return len(self._not_for_andy) >= n

    def stops(self, text: str) -> bool:
        """Words that end what Andy is doing right now: "stop" a follow, "done" shuffling the cups."""
        return getattr(self.andy, "following", False) and bool(
            STOP.search(text) or (getattr(self.andy, "playing", False) and DONE.search(text)))

    def heard(self, text: str, voice_yaw: float | None = None, level: float | None = None) -> str | None:
        """One utterance's text (and its loudness, when known). Returns what Andy said, or None if it wasn't for Andy
        (counted either way: a number)."""
        reply = self._heard(text, voice_yaw, level)
        if text.strip():
            self._count(for_andy=reply is not None)
        return reply

    def _heard(self, text: str, voice_yaw: float | None = None, level: float | None = None) -> str | None:
        text = " ".join(text.split())
        if crisis(text) and not self.stops(text) and getattr(self.andy, "following", False):
            self.andy.stop_following()  # whatever Andy is doing, this comes first
        if self.stops(text) and not crisis(text):
            self.andy.stop_following()  # no lock: the follow holds it, and this must reach it at once
            return "Stopped."
        if _looping(text):
            return None  # speech-to-text going round in circles on noise ("the state of the state of ...")
        if getattr(self.andy, "hey_only", False):  # only "Hey Andy" (or "Oye Andy"): plain "Andy" may be a person
            called = HEY_WAKE.match(text) or _hey_heard(text) or next(reversed(list(HEY_LATER.finditer(text))), None)
        else:
            called = (WAKE.match(text) or _hey_heard(text) or _soft_wake(text)
                      or next(reversed(list(LATER.finditer(text))), None))
        urgent = crisis(text) or emergency(text)  # within the window these are always heard, follow-ups used up or not
        # while filming, the director's cues are heard without the name: "take two", "cut", "that's a wrap". Called only
        # once, at the start, a later "take two" was let go if the room had talked (the clap the edit lines up on gone)
        cue = getattr(self.andy, "filming", None) is not None and _filming_cue(text)
        # crisis words and an emergency said as itself are answered without the name (November 3: someone who has
        # fallen may not say "Hey Andy"); companion/safety.py unasked_urgent keeps room talk out of it
        unasked = urgent and unasked_urgent(text)
        # November 4: with the microphone array gone faint, speech-to-text wrote words out of near-silence, and inside
        # the window after a reply Andy answered them, six in a row, talking to nobody. Without its name, a sound
        # quieter than any voice (a voice's own loudness is 0.04 to 0.14; the faint array's, under 0.01) isn't for it.
        # And it isn't the room talking either: counted as that, it closed the follow-ups after every answer.
        if level is not None and level < FAINT_LEVEL and not called:
            return None
        if not text or (not called and not (cue or unasked or self.listening() or (urgent and self._clock() <= self.awake_until))):
            if text:
                self.not_for_andy()
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
        self.follow_ups_left = self.follow_ups if called else max(0, self.follow_ups_left - 1)
        if self.talking_room():  # a conversation it isn't part of: its name each time, unless it just asked something
            asked = called and isinstance(reply, str) and reply.rstrip().endswith("?")
            self.follow_ups_left = min(self.follow_ups_left, 1 if asked else 0)
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
            if gesture and not self.busy and endpointer.active != hearing and self.listening():
                hearing = endpointer.active
                gesture("listening" if hearing else "idle")  # attentive while a follow-up is spoken
                screen = getattr(self.andy, "screen", None)
                if screen and hearing:
                    screen.doing("Listening", "Looking at you")
            if utterance is None:
                continue
            if _noise(utterance):  # never heard, never counted as the room talking; its numbers go in the journal
                self._report(None, None, utterance, endpointer, words=0)
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
            heard_at, self._again = time.monotonic(), None
            if not self.busy:
                try:
                    text = self._which_language(text, utterance, voice)
                except Exception as e:  # noqa: BLE001 - listening again is a bonus: never at the cost of the turn
                    log.warning("listening again failed: %s: %s", type(e).__name__, e)
            if self.busy:
                if text.strip() and not (crisis(text) or emergency(text)):  # those are counted when their turn runs
                    self._count(for_andy=self.stops(text))
                if crisis(text) or emergency(text):  # never dropped: stop what's running, answer it as soon as the turn ends
                    self.andy.stop_following()
                    self._pending = (text, yaw, utterance)
                    continue
                stopped = self.stops(text)
                # its length only, reported before the stop reaches the turn, so "Stopped." comes before its answer
                self._report(None, "Stopped." if stopped else None, utterance, endpointer, words=len(text.split()))
                if stopped:
                    self.andy.stop_following()  # no lock: the turn holds it, and this must reach it at once
                else:
                    self.not_for_andy()  # said over Andy's answer: most likely the room's own conversation
                continue
            self.busy = True
            self.marks = {"ended": self.utterance_end, "heard": heard_at, "again": self._again}
            turns.put((text, yaw, utterance))  # counted by heard(), when its turn says whether it was for Andy

    def _which_language(self, text: str, utterance, voice) -> str:
        """Andy was called but didn't understand: perhaps it wasn't Andy's language at all. Omnilingual ASR is asked
        again without one, and if what it writes is another of Andy's fifteen ("安迪我的眼睛在哪里"), Andy switches to it,
        says so (by hand, in it), and hears the words again in it. A request Andy understood is never asked again, and
        speech that isn't for Andy, in any language, is still dropped (it's only ever heard, never kept)."""
        from ..companion.intents import parse
        from ..companion.language import ANDY, LANGUAGES, asked_for, heard_in

        andy = self.andy
        if not hasattr(andy, "notice_language"):
            return text
        hey_only = getattr(andy, "hey_only", False)  # "Answer only to Hey Andy": a plain "Andy" may be a person
        wake, later = (HEY_WAKE, HEY_LATER) if hey_only else (WAKE, LATER)
        called = wake.match(text) or next(reversed(list(later.finditer(text))), None)
        if not called and not self.listening():
            return text  # not for Andy
        current = getattr(andy, "language", "en")
        rest = text[called.end():] if called else text
        if current == "en" and parse(rest).kind not in ("chat", "world"):
            return text  # understood: English it is
        started = time.monotonic()
        other = voice.transcribe(utterance, language="auto")
        self._again = (started, time.monotonic())
        if getattr(andy, "hood", None) is not None:
            andy.hood.heard_again(*self._again)
        if crisis(other) and not crisis(text):
            # crisis words heard only when listened to again ("앤디, 죽고 싶어요" while in English): nothing comes before
            # the crisis reply, so no "Okay, I'll speak Korean now": the language changes quietly, for the reply's sake
            code = heard_in(other)
            if code in LANGUAGES and code != current and hasattr(andy, "set_language"):
                andy.set_language(code)
            return other
        code = heard_in(other)
        if code is None or code == current or code not in LANGUAGES:
            return text
        if current == "en" and not called and not ANDY.search(other):
            return text  # away from English only when Andy was called by name ("no, no, not that one" after a find)
        back = LATER.sub("", other, count=1)
        if code == "en" and parse(back).kind in ("chat", "world") and asked_for(back) != "en":
            return text  # back to English only for a request it understands in English ("speak English" is one)
        if current != "en" and code != "en":
            # from one of Andy's other languages only back to English: Omnilingual ASR, told nothing, wrote Ukrainian as
            # Russian and could write Hindi in Urdu's letters (Arabic's), and a Latin-letter guess (Spanish for
            # Portuguese) is too easy to get wrong; "Andy, speak Korean" still switches, asked
            return text
        self.awake_until = self._clock() + self.follow_up_s  # it was called: what follows the name counts
        if asked_for(back) == code:  # "Andy, speak English" itself: the turn switches and says so, once (not twice)
            voice.language = LANGUAGES[code].asr
            return voice.transcribe(utterance)
        andy.notice_language(code)
        voice.language = getattr(andy, "asr_language", "eng_Latn")
        return voice.transcribe(utterance)  # heard again, told the language now

    def _turns(self, turns: queue.Queue, endpointer, stop) -> None:
        while not stop.is_set():
            try:
                text, yaw, utterance = turns.get(timeout=0.5)
            except queue.Empty:
                continue
            reply = None
            self.marks["began"] = time.monotonic()
            try:
                reply = self.heard(text, yaw, level=_loudness(utterance))
            except Exception as e:  # noqa: BLE001 - one bad turn must not leave Andy deaf
                log.warning("a turn failed: %s: %s", type(e).__name__, e)
            finally:
                pending, self._pending = self._pending, None
                if pending:  # crisis words said during that turn: answered now, before anything else
                    turns.put(pending)
                else:
                    self.busy = False
            self._report(text if reply is not None else None, reply, utterance, endpointer, words=len(text.split()),
                         name=_name_likeness(text))

    def _report(self, text, reply, utterance, endpointer, words: int | None = None, name: float | None = None) -> None:
        if self.on_heard:  # what wasn't for Andy: its length, its loudness, how many words were heard; never the words
            if text is None:
                x = np.abs(np.asarray(utterance, dtype=np.float32))
                level = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
                peak = float(x.max()) if len(x) else 0.0
                clipped = float(np.mean(x >= 0.98 * peak)) if peak > 0.9 else 0.0  # at the ceiling: distorted
                text = (f"{len(utterance) / endpointer.rate:.1f}s of speech, room level {endpointer.floor:.3f}, its own "
                        f"{level:.3f}, peak {peak:.2f}" + (f", {clipped:.1%} at the ceiling" if clipped else "")
                        + (f", {words} words heard" if words is not None else "")
                        + (f", closest to its name {name:.2f}" if name is not None else ""))
            self.on_heard(text, reply)


def _filming_cue(text: str) -> bool:
    """A director's cue said on its own: "take two", "next take", "cut", "that's a wrap" (companion/intents.py)."""
    from ..companion.intents import CUT, FILM_OFF, TAKE

    t = text.strip()
    return bool(TAKE.match(t) or CUT.match(t) or (FILM_OFF.search(t) and len(t.split()) <= 6))


def _name_likeness(text: str) -> float:
    """How near the nearest word heard comes to Andy's name (1.0: "andy" itself): a number for the journal, never a word."""
    from difflib import SequenceMatcher

    return max((SequenceMatcher(None, w, "andy").ratio() for w in re.findall(r"\w+", text.lower())), default=0.0)


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
