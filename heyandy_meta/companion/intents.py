"""What the person asked for, decided in code before any model sees it.

Finding, watching and forgetting things, reminders, and questions about the world each have a fixed path; everything
else is conversation. Plain rules keep the robot's actions predictable: a model never decides to move.
"""
import datetime as dt
import re
from dataclasses import dataclass

from ..agent.tools import COLOURS
from ..finder.names import KNOWN, snap

THING = r"(?:my |the |our |a |an )?(?P<thing>[a-z][a-z '\-]{1,38}?)"
FIND = re.compile(r"\b(?:where(?:'s| is| are|'re)|find|have you seen|can you see|look for|help me find|lost|misplaced|"
                  r"(?:look|search|scan)(?: around)?(?: (?:the|this|my) (?:room|house|table|desk))? for)\s+"
                  + THING
                  + r"(?:\s+(?:is|are|went|go|gone))?(?:\?|$|[,.!]| (?:please|for me|now|again))", re.I)
DRAW = re.compile(r"\b(?:draw|paint|sketch|make|create)\s+(?:me\s+|us\s+)?(?:a\s+|an\s+)?"
                  r"(?:(?:picture|drawing|painting|sketch|image)\s+of\s+)?(?P<what>.{3,200}?)[.!?]*$", re.I)
DRAW_START = re.compile(r"\b(?:draw|paint|sketch)\b|\b(?:make|create)\s+(?:me\s+|us\s+)?(?:a\s+)?"
                        r"(?:picture|drawing|painting|image)\b", re.I)
REFINE = re.compile(r"^\W*(?:(?:now|and|ok|okay)\s+)?(?:make (?:it|him|her|them|the)|add|change|turn (?:it|the)|put|give "
                    r"(?:it|him|her)|without|remove|more|less)\b", re.I)
FOLLOW = re.compile(r"\b(?:follow|track)\s+" + THING + r"(?:\s+with your eyes)?(?:\?|$|[,.!]| please)", re.I)
WATCH = re.compile(r"\bkeep (?:an )?eye on\s+" + THING + r"(?:\?|$|[,.!]| please)", re.I)
FORGET = re.compile(r"\b(?:forget|stop watching)\s+(?:where\s+)?" + THING + r"(?:\s+(?:is|are))?(?:\?|$|[,.!]| please)", re.I)
DESCRIBE = re.compile(r"\bwhat (?:am i|i'm) holding\b|\bwhat(?:'s| is| do i have)(?: this| that)? in my hands?\b|\bwhat(?:'s| is) this\b(?! (?:song|noise|sound))"
                      r"|\bwhat(?:'s| is) on the (?P<place>table|desk|counter|shelf|floor|sofa|couch|bed|chair)\b"
                      r"|\bwhat (?:can|do) you see\b|\bdescribe what you see\b|\bwhat colou?r is (?:this|it)\b", re.I)
VOICE = {  # how Andy speaks, set by voice and remembered
    "repeat": re.compile(r"\b(?:repeat that|say (?:that|it) again|what did you (?:just )?say|pardon\??$|come again|"
                         r"i didn'?t (?:catch|hear) (?:that|you))\b", re.I),
    "louder": re.compile(r"\b(?:speak up|(?:speak |talk )?louder|i can'?t hear you|turn (?:it|yourself|your voice) up)\b",
                         re.I),
    "quieter": re.compile(r"\b(?:(?:speak |talk )?(?:more )?(?:quieter|quietly|softer|softly)|too loud|turn (?:it|yourself|"
                          r"your voice) down)\b", re.I),
    "slower": re.compile(r"\b(?:(?:speak |talk )?(?:more )?slow(?:er|ly)|slow down|too fast)\b", re.I),
    "faster": re.compile(r"\b(?:(?:speak |talk )?(?:a bit |a little )?faster|speed up|too slow(?:ly)?)\b", re.I),
}
QUIET = re.compile(r"\b(?:be quiet|^\W*(?:andy\W+)?(?:please\s+)?(?:stay|keep) (?:quiet|silent)|(?:can|could|would|will) "
                   r"you (?:please )?(?:stay|keep) (?:quiet|silent)|quiet mode|leave me alone|(?:do not|don'?t) disturb(?: me)?|give me some peace|"
                   r"stop looking around)\b", re.I)
UNQUIET = re.compile(r"\b(?:you can (?:talk|look around|move) again|quiet mode off|stop being quiet|you can go back to "
                     r"normal)\b", re.I)
MOTION = {"less": re.compile(r"\b(?:move less|calm down|less movement|keep (?:still|stiller)|stop moving (?:so much|around)"
                             r"|stay (?:still|stiller))\b", re.I),
          "more": re.compile(r"\b(?:move more|more movement|be (?:more )?lively|livelier)\b", re.I)}
QUIET_FOR = re.compile(r"\bfor (?P<n>\d+|an?|one|two|three|half an) (?P<unit>minutes?|hours?)\b", re.I)
LAST_SEEN = re.compile(r"\b(?:(?:when|where) did you (?:last )?see|where did i (?:last )?(?:leave|put|have))\s+" + THING
                       + r"(?:\s+last)?(?:\?|$|[,.!]| please)", re.I)
HELP = re.compile(r"\bwhat can (?:i|you) (?:ask|say|do)\b|\bwhat do you do\b|^\W*help\W*$|\bhow do i use you\b", re.I)
REMEMBER = re.compile(r"\bwhat do you remember\b|\bwhat are you (?:keeping an eye on|watching)\b", re.I)
REMINDERS = re.compile(r"\bwhat (?:are )?(?:my|the) reminders\b|\bwhat reminders\b", re.I)
# The room in 3D (MapAnything over several looks): "show me the room", "scan the room", "my things in 3D"
ROOM = re.compile(r"\b(?:show|map|scan|measure)(?: me)? (?:the|my|this|your) (?:room|living room|space)\b|"
                  r"\b(?:room|things|space) in 3 ?d\b|\b3 ?d (?:map|view|scan|picture) of\b|"
                  r"\bwhat does (?:the|my|this) room look like\b", re.I)
# The time and the day, from the clock: the conversation's model isn't told them, and would guess.
TIME = re.compile(r"\bwhat(?:'s|s| is) the time\b(?! in\b)|\bwhat time is it\b(?! in\b)|"
                  r"\bwhat(?:'s|s| is) (?:the date|today'?s date|the day)(?: today)?\b|\bwhat day is (?:it|today)\b|"
                  r"\bwhat(?:'s|s| is) today\b(?!'s|s\b)(?!\s+\w)", re.I)  # not "today's weather", not "in Tokyo"
REMIND = re.compile(r"\bremind me\b", re.I)
PRIVACY = re.compile(r"\bwhat (?:did|have) you (?:send|sent|shared?)\b|\bwhat(?:'s| has)? (?:left|gone out of|went out of) "
                     r"(?:the|this|my) (?:house|home)\b|\bwhat (?:went|goes|has gone) (?:to|up to|out to) the "
                     r"(?:cloud|internet)\b|\bprivacy (?:report|summary|receipt)s?\b|\bwhat do you send\b", re.I)
MINE = [re.compile(r"\b(?:this|that|here)(?:'s| is) (?:my|our) " + THING + r"(?:\?|$|[,.!]| (?:please|now))", re.I),
        re.compile(r"\b(?:this|that) " + THING + r" is (?:mine|ours)\b", re.I),
        re.compile(r"\b(?:learn|remember) what (?:my|our) " + THING + r" looks? like\b", re.I),
        re.compile(r"\blearn (?:my|our) " + THING + r"(?:\?|$|[,.!]| (?:please|now|by sight))", re.I)]
POINTING = re.compile(r"\bwhat(?:'s| is) that(?: thing| one)?(?: over there| there| called)?\W*$|"
                      r"\b(?:look|see) (?:at )?(?:what|where) i(?:'?m| am) pointing\b|\bwhat am i pointing at\b|"
                      r"\b(?:look|see) over there\b|\bwhat(?:'s| is) (?:that|the thing) over there\b", re.I)
GOING_OUT = re.compile(r"\b(?:i'?m|i am|we'?re|we are) (?:just )?(?:going out|heading out|off out|popping out|leaving(?: now| "
                       r"the house)?(?=\s*(?:[,.!?]|$|for\b|to\b|in\b))|going to the (?:store|shops|supermarket|beach|bank|park|post office|mall)|off to the "
                       r"(?:store|shops|beach|park))\b|\bdo i have everything\b|\bam i forgetting anything\b|"
                       r"\bhave i got everything\b", re.I)
MAP_OF_THINGS = re.compile(r"\b(?:draw|make|paint|show)(?: me| us)? (?:a |the )?(?:map|picture|postcard|drawing) of "
                           r"(?:where )?(?:all )?(?:my|our|the) things\b|\bmap of (?:where )?(?:all )?(?:my|our) things\b", re.I)
WEB = [re.compile(r"\b(?:show|put|pull up|bring up|open|look up|display|(?:find|get)(?! my\b))\b.{2,120}?\bon (?:the|my|"
                  r"your) (?:tv|telly|screen|television)\b(?!\s*(?:stand|cabinet|unit|table|shelf|console))", re.I),
       re.compile(r"\bshow me (?:some |a few )?(?:pictures?|photos?|images?|a map|the map|a video|videos|the radar|"
                  r"the weather radar|a recipe|the recipe)\b", re.I),
       re.compile(r"\b(?:open|go to|pull up)\s+(?:the\s+)?(?:[\w-]+\.(?:com|org|net|gov|edu)|wikipedia|the news)\b", re.I)]
WEB_MORE = re.compile(r"^\W*(?:(?:now|ok(?:ay)?|and)\s+)?(?:scroll|go back|back|next page|click|tap|press|open the|zoom|"
                      r"show me more|show more|read (?:it|that|this|me)|what does (?:it|that|this) say|go to the|"
                      r"search (?:for|this page)|play (?:it|that|the))\b", re.I)
WEB_CLOSE = re.compile(r"\b(?:close (?:the |that )?(?:browser|web ?page|page|website)|take (?:it|that) off the "
                       r"(?:tv|screen))\b", re.I)
GAME = re.compile(r"\b(?:cups? game|shell game|(?:play|let'?s play)\b.{0,25}\bcups?\b|keep (?:your|an) eyes? on the ball|"
                  r"watch (?:the|my) ball|which cup|ball under (?:a|the|which|one of the) cups?)\b", re.I)
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
    kind: str  # room | time | quiet | unquiet | motion | voice | last_seen | find | follow | watch | forget | remember | reminders | remind | game | pointing | going_out | things_map | web | mine | describe | draw | help | world
    #            | chat
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
    t = re.sub(r"\buntil (minutes|hours)\b", r"in two \1", t, flags=re.I)  # "in two" heard as "until"
    return re.sub(r"\bwhere (?:am i|are i|am my|r my)\b", "where are my", t, flags=re.I)


def parse(text: str, now: dt.datetime | None = None) -> Intent:
    now = now or dt.datetime.now()
    t = normalise(text)
    if UNQUIET.search(t):
        return Intent("unquiet", text=t)
    if QUIET.search(t):
        m = QUIET_FOR.search(t)
        n = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "half an": 0.5}.get(m.group("n").lower(), None) if m else None
        n = n if n is not None else (float(m.group("n")) if m else 1.0)
        hours = n if not m or m.group("unit").lower().startswith("hour") else n / 60
        return Intent("quiet", text=t, at=hours * 3600)
    for name, rx in MOTION.items():
        if rx.search(t):
            return Intent("motion", thing=name, text=t)
    for name, rx in VOICE.items():
        if rx.search(t):
            return Intent("voice", thing=name, text=t)
    if PRIVACY.search(t):
        return Intent("privacy", text=t)
    if REMIND.search(t):
        when = parse_time(t, now)
        words = _reminder_words(when[1]) if when else ""
        if when and words:
            return Intent("remind", text=words, at=when[0], daily=bool(DAILY.search(t)))
        return Intent("remind", text="")  # asked, but the time or the words are missing: ask again
    if REMINDERS.search(t):
        return Intent("reminders")
    if re.search(r"\btime is it in\b|\bthe time in\b", t, re.I):  # somewhere else's time: looked up, never guessed
        return Intent("world", text=t)
    if TIME.search(t):
        return Intent("time", thing="day" if re.search(r"\b(?:date|day|today)\b", t, re.I) else "time")
    if ROOM.search(t) and not FIND.search(t) and not re.search(r"\bfind\b|\bwhere\b", t, re.I):
        return Intent("room", text=t)  # "scan the room for my keys" is a search, below
    if REMEMBER.search(t):
        return Intent("remember")
    if GAME.search(t):
        return Intent("game", text=t)
    if POINTING.search(t):
        return Intent("pointing", text=t)
    if MAP_OF_THINGS.search(t):
        return Intent("things_map", text=t)
    if any(rx.search(t) for rx in WEB):
        return Intent("web", text=t)
    for rx in MINE if not WATCH.search(t) else ():  # "this is my wallet, keep an eye on it" is watching
        if (m := rx.search(t)) and (thing := snap(_thing(m))).split()[-1] in KNOWN:  # a thing, not "my point"
            return Intent("mine", thing=thing, text=t)
    for kind, rx in (("forget", FORGET), ("watch", WATCH), ("follow", FOLLOW), ("last_seen", LAST_SEEN), ("find", FIND)):
        m = rx.search(t)
        if m:
            thing, place = (PLACE.split(_thing(m), maxsplit=1) + [""])[:2]  # "keys in the kitchen": thing, hint
            rest = [w for w in re.findall(r"[a-z']+", (t[:m.start()] + " " + place + " " + t[m.end():]).lower())
                    if w not in FILLER]
            hint = len(rest) >= 2 or bool(set(thing.lower().split()) & COLOURS)  # "the blue mug": which one, for compare
            return Intent(kind, thing=snap(thing.strip()), text=t, hint=kind == "find" and hint)
    if GOING_OUT.search(t):  # after finding and watching: "where are my keys? I'm going out" is a find
        return Intent("going_out", text=t)
    if m := DESCRIBE.search(t):
        return Intent("describe", thing=(m.group("place") or "").lower(), text=t)
    if DRAW_START.search(t):
        m = DRAW.search(t[DRAW_START.search(t).start():])
        if m:
            return Intent("draw", text=m.group("what").strip())
    if HELP.search(t):
        return Intent("help", text=t)
    if WORLD.search(t):
        return Intent("world", text=t)
    return Intent("chat", text=t)
