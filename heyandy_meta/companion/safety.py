"""Saying it's an AI, and the crisis protocol. Both run in code, before and outside any model.

US companion-chatbot laws (California SB 243, in effect 2026-01-01; New York, in effect 2025-11-05) ask a companion
to say it's an AI at the start and at least every three hours, and to refer anyone who talks about harming
themselves to crisis services. Andy does exactly that, and nothing more: it never counsels. The protocol is
published in docs/crisis-protocol.md.
"""
import re
import time

DISCLOSURE = "I'm Andy, an AI robot."
EVERY_S = 3 * 3600
NEW_CONVERSATION_AFTER_S = 30 * 60

CRISIS_REPLY = ("I'm a robot, so I can't help with this the way a person can. You can call or text 988, the Suicide "
                "and Crisis Lifeline, any time, day or night. If you're in danger right now, please call 911.")
CRISIS = re.compile(
    r"\b(kill(ing)? myself|end(ing)? (it all|my (own )?life)|tak(e|ing) my (own )?life|suicid\w*|hurt(ing)? myself"
    r"|harm(ing)? myself|self[- ]harm|(hang|shoot|drown|cut)(ing)? myself|overdos(e|ing) on purpose"
    r"|(don'?t|do not|no longer) want to (live|be alive|be here|wake up)|(want|going) to die|wanna die|better off dead"
    r"|wish (i was|i were|i'?d) (dead|never born)|life (isn'?t|is not|'s not|ain'?t) worth (it|living)|no reason to (live|go on)"
    r"|can'?t go on (anymore|any more|living)|end(ing)? it (all )?(tonight|today|now)|better off without me"
    r"|(sleep|go to sleep) and (never|not) wake up|never wake up again|disappear (forever|for good)"
    # Spanish (Andy can speak it): checked on the person's own words, before any translation
    r"|suicid[ao]r(me|se)?|matarme|quitarme la vida|lastimarme|hacerme da[nñ]o"
    r"|me (quiero|voy a|pienso|deseo) (matar|suicidar|morir|quitar la vida|hacer da[nñ]o|lastimar)"
    r"|(acabar|terminar) con (todo|mi vida)|no quiero (vivir|seguir viviendo|estar aqu[ií]|seguir aqu[ií])"
    r"|quiero morir(me)?|quisiera morir(me)?|ganas de morir(me)?|(estar[ií]a|quisiera estar|mejor) muert[oa]"
    r"|quisiera estar muert[oa]|ser[ií]a mejor estar muert[oa]|no vale la pena vivir|no tengo raz[oó]n para vivir"
    r"|(estar[ií]an|vivir[ií]an) mejor sin m[ií]|desaparecer para siempre|no (volver a )?despertar(me)?)\b",
    re.IGNORECASE)


def crisis(text: str) -> bool:
    t = (text or "").replace("\u2019", "'").replace("\u2018", "'")  # speech-to-text and keyboards write ’ too
    return bool(CRISIS.search(t))


class Disclosure:
    """Says "I'm Andy, an AI robot." at the start of a conversation and again every three hours."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self.last_said = self.last_turn = float("-inf")

    def prefix(self) -> str:
        now = self._clock()
        due = now - self.last_turn > NEW_CONVERSATION_AFTER_S or now - self.last_said >= EVERY_S
        self.last_turn = now
        if due:
            self.last_said = now
            return DISCLOSURE + " "
        return ""


def respond(text: str, answer, disclosure: Disclosure, opening=None, flagged: bool = False) -> str:
    """The one entry point for a spoken turn: the crisis reply bypasses the model; otherwise the model answers.
    opening, if given, is handed the AI disclosure before the answer is made, so it can be said at once. flagged: the
    second check (Llama Guard on this computer, safety_model.py) heard it where the word list didn't."""
    if flagged or crisis(text):
        disclosure.last_said = disclosure.last_turn = disclosure._clock()
        return CRISIS_REPLY
    prefix = disclosure.prefix()
    if prefix and opening:
        opening(prefix)
    return prefix + answer(text)
