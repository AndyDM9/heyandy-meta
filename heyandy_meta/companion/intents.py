"""What the person asked for, decided in code before any model sees it.

Finding, watching and forgetting things, reminders, and questions about the world each have a fixed path; everything
else is conversation. Plain rules keep the robot's actions predictable: a model never decides to move.
"""
import datetime as dt
import re
from dataclasses import dataclass

THING = r"(?:my |the |our |a |an )?(?P<thing>[a-z][a-z '\-]{1,38}?)"
FIND = re.compile(r"\b(?:where(?:'s| is| are|'re)|find|have you seen|can you see|look for|help me find|lost|misplaced)\s+"
                  + THING
                  + r"(?:\s+(?:is|are|went|go|gone))?(?:\?|$|[,.!]| (?:please|for me|now|again))", re.I)
WATCH = re.compile(r"\bkeep (?:an )?eye on\s+" + THING + r"(?:\?|$|[,.!]| please)", re.I)
FORGET = re.compile(r"\b(?:forget|stop watching)\s+(?:where\s+)?" + THING + r"(?:\s+(?:is|are))?(?:\?|$|[,.!]| please)", re.I)
REMEMBER = re.compile(r"\bwhat do you remember\b|\bwhat are you (?:keeping an eye on|watching)\b", re.I)
REMINDERS = re.compile(r"\bwhat (?:are )?(?:my|the) reminders\b|\bwhat reminders\b", re.I)
REMIND = re.compile(r"\bremind me\b", re.I)
WORLD = re.compile(r"\b(?:weather|forecast|news|headlines|score|who won|open (?:today|now|on)|opening hours|"
                   r"when (?:is|does|do|are)|what time does|latest|tonight|tomorrow|this week|look (?:it )?up|search)\b",
                   re.I)
NUMBER = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "fifteen": 15,
          "twenty": 20, "thirty": 30, "forty five": 45, "half an": 0.5}
IN = re.compile(r"\bin (?P<n>\d+|a|an|one|two|three|four|five|ten|fifteen|twenty|thirty|forty five|half an) "
                r"(?P<unit>minutes?|hours?)\b", re.I)
AT = re.compile(r"\bat (?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)?(?=\W|$)", re.I)
NOON = re.compile(r"\bat (?P<w>noon|midday|midnight)\b", re.I)
DAILY = re.compile(r"\b(?:every day|every morning|every evening|every night|daily)\b", re.I)


@dataclass(frozen=True)
class Intent:
    kind: str  # find | watch | forget | remember | reminders | remind | world | chat
    thing: str = ""
    text: str = ""  # a reminder's words, or the original request
    at: float = 0.0  # a reminder's time, epoch seconds
    daily: bool = False
    hint: bool = False  # the person said more than what to find ("by the TV", "I had them in the kitchen")


def _thing(m: re.Match) -> str:
    t = m.group("thing").strip().lower()
    return re.sub(r"\b(?:please|now|again)$", "", t).strip()


def parse_time(text: str, now: dt.datetime) -> tuple[float, str] | None:
    """When a reminder is for, and the text with the time phrase removed."""
    m = IN.search(text)
    if m:
        n = NUMBER.get(m.group("n").lower()) or float(m.group("n"))
        delta = dt.timedelta(hours=n) if m.group("unit").lower().startswith("hour") else dt.timedelta(minutes=n)
        return (now + delta).timestamp(), text[:m.start()] + text[m.end():]
    m = NOON.search(text)
    if m:
        hour, minute = (0 if m.group("w").lower() == "midnight" else 12), 0
    else:
        m = AT.search(text)
        if not m:
            return None
        hour, minute = int(m.group("h")), int(m.group("m") or 0)
        ap = (m.group("ap") or "").lower().replace(".", "")
        if hour > 23 or minute > 59 or (ap and not 1 <= hour <= 12):
            return None
        if ap == "pm" and hour != 12:
            hour += 12
        elif ap == "am" and hour == 12:
            hour = 0
        elif not ap and 1 <= hour <= 6:
            hour += 12  # "at 3" in conversation is the afternoon
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at <= now:
        at += dt.timedelta(days=1)
    return at.timestamp(), text[:m.start()] + text[m.end():]


def _reminder_words(text: str) -> str:
    text = DAILY.sub("", text)
    text = re.sub(r"^.*?\bremind me\b\s*(?:to\s+|that\s+|about\s+)?", "", text, flags=re.I)
    text = re.sub(r"^\s*(?:to|that|about)\s+", "", text.strip(), flags=re.I)
    return " ".join(text.strip(" ,.!?").split())


PLACE = re.compile(r"\s+(?=(?:in|on|by|near|next to|under|behind|beside|at|from|with|in front of)\s)")
FILLER = {"andy", "hey", "hi", "ok", "okay", "please", "um", "uh", "so", "i", "can't", "cannot", "can", "you", "think",
          "again", "now", "for", "me", "the", "my", "a", "do", "did", "have", "has", "it", "is", "are", "they", "them"}
HOURS = {w: i for i, w in enumerate(
    "one two three four five six seven eight nine ten eleven twelve".split(), 1)}
MINUTES = {"o'clock": 0, "oclock": 0, "fifteen": 15, "thirty": 30, "forty five": 45, "forty-five": 45}
SPOKEN_AT = re.compile(r"\bat (" + "|".join(HOURS) + r")(?: (" + "|".join(MINUTES) + r"))?\b", re.I)


def normalise(text: str) -> str:
    """Speech-to-text output, made readable for the rules: "at three thirty p m" -> "at 3:30 pm"."""
    t = " ".join(text.strip().split())
    t = re.sub(r"\b([ap])\.? ?m\b\.?", r"\1m", t, flags=re.I)
    t = SPOKEN_AT.sub(lambda m: f"at {HOURS[m.group(1).lower()]}:{MINUTES.get((m.group(2) or 'oclock').lower(), 0):02d}", t)
    # Heard again and again for "where are my" (Omnilingual ASR, all sizes, 2026-10-27).
    t = re.sub(r"\bwears (the|my|our)\b", r"where's \1", t, flags=re.I)
    return re.sub(r"\bwhere (?:am i|are i|am my|r my)\b", "where are my", t, flags=re.I)


def parse(text: str, now: dt.datetime | None = None) -> Intent:
    now = now or dt.datetime.now()
    t = normalise(text)
    if REMIND.search(t):
        when = parse_time(t, now)
        words = _reminder_words(when[1]) if when else ""
        if when and words:
            return Intent("remind", text=words, at=when[0], daily=bool(DAILY.search(t)))
        return Intent("remind", text="")  # asked, but the time or the words are missing: ask again
    if REMINDERS.search(t):
        return Intent("reminders")
    if REMEMBER.search(t):
        return Intent("remember")
    for kind, rx in (("forget", FORGET), ("watch", WATCH), ("find", FIND)):
        m = rx.search(t)
        if m:
            thing, place = (PLACE.split(_thing(m), maxsplit=1) + [""])[:2]  # "keys in the kitchen": thing, hint
            rest = [w for w in re.findall(r"[a-z']+", (t[:m.start()] + " " + place + " " + t[m.end():]).lower())
                    if w not in FILLER]
            return Intent(kind, thing=thing.strip(), text=t, hint=kind == "find" and len(rest) >= 2)
    if WORLD.search(t):
        return Intent("world", text=t)
    return Intent("chat", text=t)
