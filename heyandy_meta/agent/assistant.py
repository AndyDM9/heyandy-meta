"""Andy's agent: requests with more than one part, planned over all of the robot's abilities.

"Find my glasses, and remind me at 5 to clean them." "Good morning, Andy." A single rule can't do these, so Muse Spark
(online) or Muse Glimmer (on this computer) gets the robot's abilities as tools and does them in order: finding,
following, looking and telling, keeping an eye on things, reminders, pictures and looking things up. Each tool is the
same code the simple paths use, so it moves the body, checks its arguments and speaks its own short acknowledgements;
the model sees only the tools' words, and ends with a short spoken sentence built from them.
"""
import datetime as dt
import json
import re
import time
from dataclasses import dataclass, field

from ..budget import Budget, chat_cost
from ..companion.intents import DESCRIBE, DRAW_START, REMEMBER, REMIND, REMINDERS, WORLD, normalise, parse_time
from ..companion.reminders import spoken_time
from ..models.retry import with_retry

# Loose on purpose: these only notice that more than one thing was asked; the tools do the exact parsing.
ABILITIES = {
    "find": re.compile(r"\b(?:where(?:'s| is| are|'re)|find|have you seen|look for|lost|misplaced)\b", re.I),
    "follow": re.compile(r"\b(?:follow|track)\b", re.I),
    "watch": re.compile(r"\bkeep (?:an )?eye on\b", re.I),
    "forget": re.compile(r"\b(?:forget|stop watching)\b", re.I),
    "describe": DESCRIBE, "draw": DRAW_START, "remind": REMIND, "reminders": REMINDERS, "remember": REMEMBER,
    "world": WORLD}
MORNING = re.compile(r"^\W*(?:(?:hey|hi|hello)\s+)?(?:andy[\s,]*)?good morning\b", re.I)
JOINED = re.compile(r"\b(?:and then|then|after that|and also|also|and)\b", re.I)

SYSTEM = ("You are Andy, a small tabletop robot in someone's home in the United States. Do what the person asked, in "
          "order, using the tools: they move the robot and report back. Only the tools act; never say you did "
          "something a tool didn't report. When you're done, reply with one or two short, warm spoken sentences "
          "built only from what the tools returned. No lists or markdown. Never give medical advice.")
MORNING_BRIEF = ("It's the person's first good morning today. Greet them, then give a short morning briefing: look up "
                 "today's weather, list today's reminders, and say where the things you keep an eye on were last "
                 "seen. Keep it to three or four short sentences.")


def _fn(name, description, **props):
    required = [k for k, v in props.items() if not v.pop("optional", False)]
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props, "required": required}}}


S = {"type": "string"}
TOOLS = [
    _fn("find", "Look around the room for a thing and point at it.", object=dict(S),
        hint={**S, "description": "anything the person said about where it might be", "optional": True}),
    _fn("follow", "Follow a thing with the robot's eyes while the person moves it.", object=dict(S)),
    _fn("look_and_tell", "Look and say what is there.",
        where={"type": "string", "enum": ["in my hands", "on the table", "in front of you"]}),
    _fn("keep_an_eye_on", "Remember where a thing is whenever the robot sees it.", object=dict(S)),
    _fn("forget", "Stop keeping an eye on a thing and forget where it was.", object=dict(S)),
    _fn("what_i_remember", "Where the things the robot keeps an eye on were last seen."),
    _fn("set_reminder", "Remind the person, in person, at a time.", what=dict(S),
        when={**S, "description": "as the person said it: 'at 5 pm', 'in 10 minutes', 'at noon'"}),
    _fn("list_reminders", "The person's upcoming reminders."),
    _fn("draw", "Make a picture from words and show it on the TV.", picture=dict(S)),
    _fn("look_up", "Look something up on the web (weather, opening hours, news).", question=dict(S)),
]


def where_they_live(home: str) -> str:
    if home:
        return f"The person lives in {home}."
    return "You don't know where the person lives: for weather or anything local, ask them instead of guessing."


def needs_agent(text: str) -> bool:
    """More than one thing asked at once ("find my keys and remind me at 5"), or the day's first good morning."""
    t = normalise(text)
    asked = {name for name, rx in ABILITIES.items() if rx.search(t)}
    if "remind" in asked:
        asked.discard("reminders")
    return len(asked) >= 2 and bool(JOINED.search(t))


@dataclass
class Turn:
    reply: str
    steps: list = field(default_factory=list)  # (tool, arguments, result)
    calls: int = 0


class Assistant:
    def __init__(self, andy):
        self.andy = andy

    def _tools(self) -> dict:
        a = self.andy
        now = lambda: dt.datetime.fromtimestamp(a.clock())  # noqa: E731

        def remind(what, when):
            at = parse_time(f"remind me {when}", now())
            if not at:
                return f"refused: I couldn't tell when '{when}' is; ask the person for a time"
            r = a.reminders.add(re.sub(r"^\s*(?:to|that|about)\s+", "", what, flags=re.I), at[0], now=a.clock())
            return f"Reminder set for {spoken_time(r.at)}: {r.text}."

        def remember():
            lines = a._memory()
            a.screen.remember_list(lines)
            return "; ".join(lines) or "I'm not keeping an eye on anything."

        def watch(object):
            a.places.watch(object.lower())
            return f"Keeping an eye on the {object}."

        def forget(object):
            a.places.forget(object.lower())
            return f"Forgot the {object}."

        def reminders():
            up = a.reminders.upcoming()[:5]
            return "; ".join(f"at {spoken_time(r.at)}: {r.text}" for r in up) or "No reminders."

        return {
            "find": lambda object, hint="": a.find(object.lower(), hint or f"where is the {object}", hint=bool(hint)),
            "follow": lambda object: a.follow(object.lower(), seconds=20.0),
            "look_and_tell": lambda where: a.describe("table" if "table" in where else "", holding="hand" in where),
            "keep_an_eye_on": watch, "forget": forget, "what_i_remember": remember,
            "set_reminder": remind, "list_reminders": reminders,
            "draw": lambda picture: a.draw(picture),
            "look_up": lambda question: a.look_up(question),
        }

    def run(self, client, request: str, model: str, paid: bool, budget: Budget | None = None,
            brief: bool = False, max_calls: int = 8, sleep=time.sleep) -> Turn:
        budget, tools, turn = budget or Budget(), self._tools(), Turn("")
        system = SYSTEM + " " + where_they_live(self.andy.home) + (" " + MORNING_BRIEF if brief else "")
        messages = [{"role": "system", "content": system if paid else "Reasoning effort: low. " + system},
                    {"role": "user", "content": request}]
        extra = {"reasoning_effort": "low"} if paid else {}
        while turn.calls < max_calls:
            if paid:
                budget.check(chat_cost(model, sum(len(str(m.get("content") or "")) for m in messages) // 2 + 800, 2000))
            out = with_retry(lambda: client.chat.completions.create(model=model, messages=messages, tools=TOOLS,
                                                                    max_tokens=2000, **extra), sleep=sleep)
            turn.calls += 1
            if paid:
                usage = getattr(out, "usage", None)
                budget.record(model, chat_cost(model, getattr(usage, "prompt_tokens", 0) or 0,
                                               getattr(usage, "completion_tokens", 0) or 0))
            msg = out.choices[0].message
            calls = getattr(msg, "tool_calls", None) or []
            if not calls:
                turn.reply = (msg.content or "").strip()
                return turn
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls]})
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                    fn = tools.get(c.function.name)
                    result = fn(**args) if fn else f"refused: there is no tool called {c.function.name!r}"
                except (TypeError, ValueError, json.JSONDecodeError) as e:
                    args, result = {}, f"refused: {type(e).__name__}"
                turn.steps.append((c.function.name, args, str(result)))
                messages.append({"role": "tool", "tool_call_id": c.id, "content": str(result)})
        turn.reply = "I did what I could; some of it didn't finish."
        return turn
