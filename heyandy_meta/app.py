"""Andy, one turn at a time: from what the person said to what the robot does in the room and says.

Every turn goes through the safety layer first (the crisis protocol, saying it's an AI). Then the request is sorted
in code (companion/intents.py) and takes a fixed path: finding things moves the body; reminders are kept and
delivered in person; questions about the world use Muse Spark's web search; anything else is conversation, on
Glimmer unless it needs more thought. When the cloud is refused or unreachable, the device answers instead.

Pictures from the home go only to models on this computer (SAM 3.1 and Glimmer); Muse Spark gets words.
"""
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
from .companion.safety import Disclosure, respond
from .finder.search import Finder, Found, Segmenter
from .memory.glance import glance
from .memory.places import Places
from .models.common import Chat, Reply
from .models.retry import CloudUnavailable
from .router import Router
from .robot.body import Body
from .screen.state import ScreenState

GLANCE_EVERY_S = 5 * 60
CLOUD_TROUBLE = (BudgetExceeded, CloudUnavailable, APIError, RuntimeError)  # RuntimeError: no key set


class NoCloud:
    """Stands in for Muse Spark when there's no key or the robot is offline: the router falls back to the device."""

    def chat(self, prompt: str) -> Reply:
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
    budget: Budget = field(default_factory=Budget)
    online: bool = True
    clock: object = time.time

    def __post_init__(self):
        self.finder = Finder(self.body, self.segmenter, check=self.judge.real if self.judge else None)
        self.router = Router(self.device, self.cloud or NoCloud())
        self.disclosure = Disclosure(self.clock)
        self._last_glance = self.clock()
        self._source = self._reason = ""

    # --- a turn ---

    def hear(self, text: str) -> str:
        self.reminders.mention_missed(self.say)
        self._source = self._reason = ""
        reply = respond(text, self._answer, self.disclosure)
        self.say(reply)
        return reply

    def say(self, text: str) -> None:
        self.body.say(text)
        self.screen.said(text, self._source, self._reason)

    def _answer(self, text: str) -> str:
        i = parse(text, _now(self.clock))
        if i.kind == "find":
            return self.find(i.thing, text)
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
                return "What should I remind you about, and when?"
            r = self.reminders.add(i.text, i.at, i.daily, now=self.clock())
            return f"I'll remind you {'every day ' if r.daily else ''}at {spoken_time(r.at)}: {r.text}."
        if i.kind == "world":
            return self.look_up(text)
        return self.talk(text)

    def talk(self, text: str) -> str:
        try:
            reply = self.router.answer(text, self.online)
        except APIError:
            return "I'm having trouble thinking just now. Could you say that again in a minute?"
        self._source, self._reason = reply.source, self.router.last.reason
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
        self.screen.answered(ans.text, ans.sources, "cloud", self._reason)
        return ans.spoken

    def find(self, thing: str, request: str) -> str:
        self.screen.clear()
        self.screen.timer_start()
        found, words = None, ""
        if self.online and self.spark is not None:
            tools = SearchTools(self.finder, self.places, self.judge)
            try:
                plan = plan_search(self.spark, request, tools, budget=self.budget)
            except CLOUD_TROUBLE as e:
                self.screen.step(f"the cloud planner is unavailable ({type(e).__name__}); searching on my own")
            else:
                for tool, args, result in plan.steps:
                    self.screen.step(f"{tool}: {result}")
                found, words = tools.pointed, plan.reply
                self._source, self._reason = "cloud", "search planned by Muse Spark; pictures checked here"
                if found is None:
                    self.screen.timer_stop()
                    return words or self._not_found(thing)
        if found is None:
            self._source, self._reason = "device", "fixed search on this computer"
            last = self.places.last_seen(thing)
            self.screen.step("recall: " + (f"last seen {side(last[0])}" if last else "no recent sighting"))
            found = self.finder.find(thing, last)
            self.screen.step(f"looked {self.finder.looks} times" + (f"; {self.finder.why}" if self.finder.why else ""))
        self.screen.timer_stop()
        if found is None:
            return self._not_found(thing)
        self.places.saw(found.label, found.yaw, found.pitch)
        words = words or self._found_words(found)
        self.screen.found(found, words)
        return words

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
            last = self.places.last_seen(label)
            lines.append(f"{label}: " + (f"last seen {side(last[0])}" if last else "not seen yet"))
        return lines

    # --- between turns ---

    def tick(self) -> None:
        """Deliver reminders that are due, and glance around now and then for watched things."""
        now = self.clock()
        for r in self.reminders.due(now):
            self.reminders.deliver(r, lambda: face_person(self.body, self.segmenter), self.say, now)
        if self.places.watching() and now - self._last_glance >= GLANCE_EVERY_S:
            self._last_glance = now
            glance(self.body, self.segmenter, self.places)


def _now(clock):
    import datetime as dt

    return dt.datetime.fromtimestamp(clock())


def _join(items: list[str]) -> str:
    items = [f"your {x}" for x in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _it(thing: str) -> str:
    return "them" if thing.endswith("s") and not thing.endswith("ss") else "it"
