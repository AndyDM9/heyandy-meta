"""Andy, one turn at a time: from what the person said to what the robot does in the room and says.

Every turn goes through the safety layer first (the crisis protocol, saying it's an AI). Then the request is sorted
in code (companion/intents.py) and takes a fixed path: finding things moves the body; reminders are kept and
delivered in person; questions about the world use Muse Spark's web search; anything else is conversation, on
Glimmer unless it needs more thought. When the cloud is refused or unreachable, the device answers instead.

Pictures from the home go only to models on this computer (SAM 3.1 and Glimmer); Muse Spark gets words.
"""
import re
import threading
import time
from dataclasses import dataclass, field

from openai import APIError

from .agent.loop import plan_search
from .agent.tools import SearchTools, side
from .budget import Budget, BudgetExceeded
from .companion import answers
from .companion.attention import face_person
from .companion.intents import parse
from .companion.reminders import Reminders, spoken_time
from .companion.safety import DISCLOSURE, Disclosure, respond
from .finder.search import Finder, Found, Segmenter
from .memory.glance import glance
from .memory.places import Places
from .models.common import Chat, Reply
from .models.retry import CloudUnavailable
from .router import Router
from .robot.body import Body
from .screen.state import ScreenState

GLANCE_EVERY_S = 5 * 60
ANSWER_WITHIN_S = 60  # how long Andy's question ("remind you about what, and when?") waits for the answer
# A chat model claiming an action only the robot's own code takes (it set nothing; Andy's code would have said so).
CLAIMS = re.compile(r"\b(?:i'?ll|i will|i'?ve|i have|i'?m going to|got it[,.]? i'?ll)\s+(?:\w+\s+){0,2}?"
                    r"(?:remind|set (?:a|the|your)|keep an eye|watch|look for|find|found|search|point)\b", re.I)
HISTORY_TURNS, HISTORY_FORGET_S = 4, 30 * 60  # a conversation: its last few exchanges, forgotten after 30 quiet minutes
CLOUD_TROUBLE = (BudgetExceeded, CloudUnavailable, APIError, RuntimeError)  # RuntimeError: no key set


class NoCloud:
    """Stands in for Muse Spark when there's no key or the robot is offline: the router falls back to the device."""

    def chat(self, prompt: str, history=()) -> Reply:
        raise CloudUnavailable("no Model API key on this computer", [])


@dataclass
class Andy:
    body: Body
    segmenter: Segmenter
    device: Chat  # Muse Glimmer on this computer
    places: Places
    reminders: Reminders
    screen: ScreenState = field(default_factory=ScreenState)
    cloud: Chat | None = None  # Muse Spark for conversation
    spark: object | None = None  # the Model API client, for planning searches and web answers (words only)
    judge: object | None = None  # Glimmer's picture checks, on this computer
    glimmer: object | None = None  # the local llama-server client, for Glimmer planning searches itself
    budget: Budget = field(default_factory=Budget)
    online: bool = True
    clock: object = time.time

    def __post_init__(self):
        self.finder = Finder(self.body, self.segmenter, check=self.judge.real if self.judge else None)
        self.router = Router(self.device, self.cloud or NoCloud())
        self.disclosure = Disclosure(self.clock)
        self._last_glance = self.clock()
        self._source = self._reason = ""
        self.lock = threading.RLock()  # one thing at a time moves the body: keyboard, voice or a reminder
        self.history: list[tuple[str, str]] = []  # this conversation, in memory only
        self._asked: tuple[str, float] | None = None  # a question Andy asked, waiting for its answer
        self.person: tuple[float, float] | None = None  # where the person is (yaw, pitch), to face them when talking
        self._pointed = False  # this turn pointed at something
        self.hold_point_s = 1.2 if hasattr(self.body, "motion") else 0.0  # the real robot holds a point a moment
        self._last_turn = float("-inf")

    # --- a turn ---

    def hear(self, text: str) -> str:
        with self.lock:
            self.screen.new_turn()
            if self.clock() - self._last_turn > HISTORY_FORGET_S:
                self.history = []  # a new conversation
            self._last_turn = self.clock()
            self.reminders.mention_missed(self.say)
            self._source = self._reason = ""
            self._pointed = False
            reply = respond(text, self._answer, self.disclosure)
            self.face_person_to_speak()
            self.say(reply)
            # The "I'm Andy, an AI robot." opening is the code's, not the model's: kept out so it isn't copied.
            self.history = (self.history + [(text, reply.removeprefix(DISCLOSURE).strip())])[-HISTORY_TURNS:]
            return reply

    def turn_to_person(self, yaw: float, pitch: float | None = None) -> None:
        """Turn towards the person without waiting: within the head's reach the body-language loop eases the head
        there; further round, the turn runs on its own thread. Either way the answer is being made meanwhile."""
        pitch = pitch if pitch is not None else (self.person[1] if self.person else -5.0)
        self.person = (yaw, pitch)
        face = getattr(self.body, "face", None)
        base = getattr(self.body, "_sent", (0.0, 0.0, 0.0))[2]
        if face and abs(yaw - base) <= getattr(self.body, "head_yaw", 30.0):
            face(yaw, pitch)
        elif face:
            threading.Thread(target=self.body.look, args=(yaw, pitch), kwargs={"precise": False}, daemon=True).start()
        else:
            self.body.look(yaw, pitch, precise=False)

    def face_person_to_speak(self) -> None:
        """Speak to the person, not to the thing: after pointing, hold it a moment, then turn to them."""
        if self.person is None:
            return
        yaw, pitch = self.person
        if abs(getattr(self.body, "yaw", yaw) - yaw) > 8 or abs(getattr(self.body, "pitch", pitch) - pitch) > 8:
            if self._pointed:
                time.sleep(self.hold_point_s)
            self.body.look(yaw, pitch, precise=False)
        face = getattr(self.body, "face", None)
        if face:
            face(yaw, pitch)  # and keep easing towards them while talking

    def say(self, text: str) -> None:
        self.body.say(text)
        self.screen.said(text, self._source, self._reason)

    def _answer(self, text: str) -> str:
        i = parse(text, _now(self.clock))
        if self._asked and i.kind == "chat" and self.clock() - self._asked[1] <= ANSWER_WITHIN_S:
            i = parse(self._asked[0] + " " + text, _now(self.clock))  # the answer to Andy's question
        self._asked = None
        if i.kind == "find":
            return self.find(i.thing, text, i.hint)
        if i.kind == "watch":
            self.places.watch(i.thing)
            return (f"I'll keep an eye on your {i.thing}. I only remember where I last saw {_it(i.thing)}, "
                    f"never a picture. Say 'forget my {i.thing}' to stop.")
        if i.kind == "forget":
            self.places.forget(i.thing)
            self.screen.remember_list(self._memory())
            return f"I've forgotten your {i.thing}."
        if i.kind == "remember":
            lines = self._memory()
            self.screen.remember_list(lines)
            return ("I'm keeping an eye on " + _join(self.places.watching()) + ". It's on the screen.") if lines \
                else "I'm not keeping an eye on anything. Say 'keep an eye on my keys' to start."
        if i.kind == "reminders":
            up = self.reminders.upcoming()[:5]
            if not up:
                return "You have no reminders."
            return "Your reminders: " + "; ".join(f"at {spoken_time(r.at)}, {r.text}" for r in up) + "."
        if i.kind == "remind":
            if not i.text:
                self._asked = ("remind me", self.clock())
                return "What should I remind you about, and when?"
            r = self.reminders.add(i.text, i.at, i.daily, now=self.clock())
            return f"I'll remind you {'every day ' if r.daily else ''}at {spoken_time(r.at)}: {r.text}."
        if i.kind == "world":
            return self.look_up(text)
        return self.talk(text)

    def talk(self, text: str) -> str:
        try:
            reply = self.router.answer(text, self.online, self.history)
        except APIError:
            return "I'm having trouble thinking just now. Could you say that again in a minute?"
        self._source, self._reason = reply.source, self.router.last.reason
        self.screen.used("Muse Spark" if reply.source == "cloud" else "Muse Glimmer", reply.source)
        if CLAIMS.search(reply.text):
            self._reason += "; a promise the model can't keep was replaced"
            return ("I can't do that from a chat. Say it to me directly, like: Andy, remind me in ten minutes to "
                    "stretch, or: Andy, where are my keys?")
        return reply.text

    def look_up(self, question: str) -> str:
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "offline: no web search"
            return "I can't look things up right now, because I'm not connected."
        try:
            ans = answers.ask(self.spark, question, budget=self.budget)
        except CLOUD_TROUBLE:
            self._source, self._reason = "device", "the web search didn't answer"
            return "I couldn't look that up just now. Please try again in a little while."
        self._source, self._reason = "cloud", "web search (Muse Spark)"
        self.screen.used("Muse Spark + web search", "cloud")
        self.screen.answered(ans.text, ans.sources, "cloud", self._reason)
        return ans.spoken

    def planners(self) -> list[tuple]:
        """Who can plan a search with the tools, best first: Muse Spark online, then Muse Glimmer on this computer."""
        out = []
        if self.online and self.spark is not None:
            out.append((self.spark, "muse-spark-1.3", True, "cloud", "search planned by Muse Spark; pictures checked here"))
        if self.glimmer is not None:
            out.append((self.glimmer, "muse-glimmer-30B", False, "device", "search planned by Muse Glimmer on this computer"))
        return out

    def gesture(self, name: str) -> None:
        g = getattr(self.body, "gesture", None)
        if g:
            g(name)

    def find(self, thing: str, request: str, hint: bool = False) -> str:
        """A plain "where are my keys" gets the fast fixed sweep; a request with a hint gets an agent that uses it."""
        self.screen.clear()
        self.screen.timer_start()
        checks = getattr(self.judge, "calls", 0)
        self.finder.looks = 0
        self.say("Let me look.")  # answer at once: a search takes a few seconds
        self.gesture("thinking")
        try:
            return self._find(thing, request, hint, checks)
        finally:
            self.gesture("idle")

    def _find(self, thing: str, request: str, hint: bool, checks: int) -> str:
        found, words = None, ""
        for client, model, paid, source, reason in (self.planners() if hint else []):
            tools = SearchTools(self.finder, self.places, self.judge, on_tool=self._tool_moves)
            try:
                plan = plan_search(client, request, tools, model=model, budget=self.budget, paid=paid)
            except CLOUD_TROUBLE as e:
                self.screen.step(f"{model} is unavailable ({type(e).__name__})")
                continue
            for tool, args, result in plan.steps:
                self.screen.step(f"{tool}: {result}")
            found, words = tools.pointed, ""  # found: Andy's words come from the tools, never the model's guesses
            self.screen.used(("Muse Spark" if paid else "Muse Glimmer") + " (plans)", source, plan.calls)
            self._source, self._reason = source, reason
            if found is None:
                self.screen.timer_stop()
                return plan.reply or self._not_found(thing)
            break
        if found is None:
            self._source, self._reason = "device", "fixed search on this computer"
            last = self.places.last_seen(thing)
            self.screen.step("recall: " + (f"last seen {side(last[0])}" if last else "no recent sighting"))
            self.gesture("searching")
            found = self.finder.find(thing, last)
            self.screen.step(f"looked {self.finder.looks} times" + (f"; {self.finder.why}" if self.finder.why else ""))
        self.screen.timer_stop()
        self.screen.used("SAM 3.1", "device", self.finder.looks)
        self.screen.used("Muse Glimmer (picture check)", "device", getattr(self.judge, "calls", 0) - checks)
        if found is None:
            return self._not_found(thing)
        self.places.saw(found.label, found.yaw, found.pitch, when=self.clock())
        self._pointed = True
        self.gesture("found")
        words = words or self._found_words(found)
        self.screen.found(found, words)
        return words

    def _tool_moves(self, starting: bool) -> None:
        """Still while a tool looks; thinking while the model decides what to do next."""
        self.gesture("searching" if starting else "thinking")

    def _found_words(self, f: Found) -> str:
        where = side(f.yaw)
        if not f.reachable:
            return f"I can't turn far enough to point, but your {f.label} is {where}."
        return f"I see your {f.label}, {where}." + (" Right where I last saw it." if f.remembered else "")

    def _not_found(self, thing: str) -> str:
        if "picture" in self.finder.why:
            return f"I only saw a picture of {thing} on a screen. Could you tell me where you last had {_it(thing)}?"
        return f"I couldn't find your {thing}. Could you tell me where you last had {_it(thing)}?"

    def _memory(self) -> list[str]:
        lines = []
        for label in self.places.watching():
            last, at = self.places.last_seen(label, now=self.clock()), self.places.seen_at(label)
            lines.append(f"{label}: " + (f"seen {_ago(self.clock() - at)}, {side(last[0])}" if last else "not seen yet"))
        return lines

    # --- between turns ---

    def tick(self) -> None:
        """Deliver reminders that are due, and glance around now and then for watched things."""
        with self.lock:
            self._tick()

    def _tick(self) -> None:
        now = self.clock()
        for r in self.reminders.due(now):
            self.reminders.deliver(r, self._find_person, self.say, now)
        if self.places.watching() and now - self._last_glance >= GLANCE_EVERY_S:
            self._last_glance = now
            self.gesture("searching")
            try:
                glance(self.body, self.segmenter, self.places)
            finally:
                self.gesture("idle")

    def _find_person(self):
        self.gesture("searching")
        try:
            direction = face_person(self.body, self.segmenter)
        finally:
            self.gesture("idle")
        if direction:
            self.person = direction
        return direction


def _now(clock):
    import datetime as dt

    return dt.datetime.fromtimestamp(clock())


def _join(items: list[str]) -> str:
    items = [f"your {x}" for x in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' * (minutes != 1)} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' * (hours != 1)} ago"


def _it(thing: str) -> str:
    return "them" if thing.endswith("s") and not thing.endswith("ss") else "it"
