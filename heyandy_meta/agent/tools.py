"""The tools Muse Spark may use to plan a search. They name views and places, never angles or motor values.

Every argument is checked here, in code: an unknown view, place or tool, or an odd object name, is refused with a
reason the model can read, and nothing moves.
"""
import re
from dataclasses import dataclass, field
from typing import Protocol

from ..finder.search import Finder, Found
from ..memory.places import Places
from ..models.common import Mask
from ..robot.body import Frame

VIEWS = {  # name -> (yaw, pitch); the names are what the model sees
    "far left": (55.0, 15.0),
    "left": (18.0, 15.0),
    "right": (-18.0, 15.0),
    "far right": (-55.0, 15.0),
    "behind left": (110.0, 15.0),
    "behind right": (-110.0, 15.0),
    "floor in front": (0.0, 32.0),
}
OBJECT = re.compile(r"^[a-zA-Z][a-zA-Z '\-]{0,39}$")  # a short noun phrase for SAM 3.1
DESCRIPTION = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 ,'\-]{0,79}$")  # the person's words about which one


class Judge(Protocol):
    """Picture checks that run on this computer (Glimmer); the model planning the search only sees the answer."""

    def pick(self, found: list[tuple[Frame, Mask]], description: str) -> int | None: ...


def side(yaw: float) -> str:
    if abs(yaw) < 10:
        return "straight ahead"
    side = "left" if yaw > 0 else "right"
    if abs(yaw) > 90:
        return f"behind me on my {side}"
    return f"to my {side}" if abs(yaw) > 35 else f"a little to my {side}"


SPECS = [
    {"type": "function", "function": {
        "name": "recall", "description": "Where a watched object was last seen, if the person asked the robot to keep an eye on it.",
        "parameters": {"type": "object", "properties": {"object": {"type": "string"}}, "required": ["object"]}}},
    {"type": "function", "function": {
        "name": "look", "description": "Turn to one or more views and look for an object. Returns numbered places where it might be.",
        "parameters": {"type": "object", "properties": {
            "object": {"type": "string", "description": "A short noun phrase, e.g. 'reading glasses' or 'glasses case'."},
            "views": {"type": "array", "items": {"type": "string", "enum": list(VIEWS)}}},
            "required": ["object", "views"]}}},
    {"type": "function", "function": {
        "name": "look_closer", "description": "Turn straight at a numbered place (or 'remembered') and check the object "
        "is really there. If it is, the robot points at it and the search is done.",
        "parameters": {"type": "object", "properties": {"object": {"type": "string"}, "place": {"type": "string"}},
                       "required": ["object", "place"]}}},
    {"type": "function", "function": {
        "name": "compare", "description": "When several numbered places might hold the object, look closely at each "
        "and pick the one that fits the person's description (colour, what it's next to). The pictures are checked on "
        "the robot's own computer; you get back only which place fits.",
        "parameters": {"type": "object", "properties": {
            "object": {"type": "string"},
            "description": {"type": "string", "description": "The person's words, e.g. 'blue, next to the laptop'."},
            "places": {"type": "array", "items": {"type": "string"}}},
            "required": ["object", "description", "places"]}}},
    {"type": "function", "function": {
        "name": "point", "description": "Point at a place that look_closer confirmed. Only confirmed places can be pointed at.",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}}, "required": ["place"]}}},
]


@dataclass
class SearchTools:
    finder: Finder
    places: Places | None = None
    judge: Judge | None = None
    candidates: dict[str, tuple[float, float]] = field(default_factory=dict)
    confirmed: dict[str, Found] = field(default_factory=dict)
    pointed: Found | None = None
    auto_point: bool = True  # a confirmed closer look points at once: one model call fewer

    def specs(self) -> list[dict]:
        """The tools to offer: recall only when something is being watched."""
        watching = bool(self.places and self.places.watching())
        return [s for s in SPECS if watching or s["function"]["name"] != "recall"]

    def call(self, name: str, args: dict) -> str:
        handler = {"recall": self._recall, "look": self._look, "look_closer": self._closer, "compare": self._compare,
                   "point": self._point}.get(name)
        if handler is None:
            return f"refused: there is no tool called {name!r}"
        try:
            return handler(**args)
        except TypeError:
            return f"refused: wrong arguments for {name}"

    def _object(self, obj) -> str | None:
        return obj.strip().lower() if isinstance(obj, str) and OBJECT.match(obj.strip()) else None

    def _recall(self, object) -> str:
        obj = self._object(object)
        if obj is None:
            return "refused: the object must be a short plain noun phrase"
        last = self.places.last_seen(obj) if self.places else None
        if last is None:
            return f"I have no recent sighting of the {obj}."
        self.candidates["remembered"] = last
        return f"Last seen {side(last[0])}. Place 'remembered'; check it with look_closer."

    def _look(self, object, views) -> str:
        obj = self._object(object)
        if obj is None:
            return "refused: the object must be a short plain noun phrase"
        if not isinstance(views, list) or not views or any(v not in VIEWS for v in views):
            return f"refused: views must be chosen from {list(VIEWS)}"
        found = self.finder.scan(obj, [VIEWS[v] for v in dict.fromkeys(views)])
        if not found:
            return f"No {obj} seen in: {', '.join(views)}."
        lines = []
        for s in found[:5]:
            pid = str(len(self.candidates) + 1)
            self.candidates[pid] = (s.yaw, s.pitch)
            lines.append(f"place {pid}: {side(s.yaw)}, confidence {s.score:.2f}, seen in {s.views} view(s)")
        return "Possible " + obj + ": " + "; ".join(lines)

    def _closer(self, object, place) -> str:
        obj = self._object(object)
        if obj is None:
            return "refused: the object must be a short plain noun phrase"
        if place not in self.candidates:
            return f"refused: no place {place!r}; places so far: {list(self.candidates) or 'none'}"
        found = self.finder.confirm(obj, *self.candidates[place])
        if found is None:
            return f"Looked closer at place {place}: {self.finder.why or 'not there'}."
        self.confirmed[place] = found
        if self.auto_point:
            return "Confirmed. " + self._point(place)
        return f"Confirmed: the {obj} is at place {place}, {side(found.yaw)}."

    def _compare(self, object, description, places) -> str:
        obj = self._object(object)
        if obj is None:
            return "refused: the object must be a short plain noun phrase"
        if not isinstance(description, str) or not DESCRIPTION.match(description.strip()):
            return "refused: the description must be a few plain words"
        if not isinstance(places, list) or not 2 <= len(places) <= 4 or any(p not in self.candidates for p in places):
            return f"refused: give 2 to 4 places from {list(self.candidates) or 'none'}"
        if self.judge is None:
            return "I can't compare pictures right now; look_closer at the likeliest place instead."
        seen, notes = [], []
        for p in dict.fromkeys(places):
            found = self.finder.confirm(obj, *self.candidates[p])
            if found is None:
                notes.append(f"place {p}: {self.finder.why}")
                continue
            self.confirmed[p] = found
            seen.append(p)
        if not seen:
            return "Compared: " + "; ".join(notes) + "."
        i = self.judge.pick([(self.confirmed[p].frame, self.confirmed[p].mask) for p in seen], description.strip())
        for p in seen:
            if i is None or p != seen[i]:
                self.confirmed.pop(p)  # only the one that fits may be pointed at
        if i is None:
            return f"Compared places {', '.join(seen)}: none looks like '{description.strip()}'. Ask the person."
        return f"Place {seen[i]} fits '{description.strip()}' and is confirmed, {side(self.confirmed[seen[i]].yaw)}."

    def _point(self, place) -> str:
        found = self.confirmed.get(place)
        if found is None:
            return f"refused: place {place!r} isn't confirmed; use look_closer first"
        self.pointed = self.finder.point(found)
        if self.places:
            self.places.saw(found.label, found.yaw, found.pitch)
        if not found.reachable:
            return f"I can't turn far enough to point; it's {side(found.yaw)}. Tell the person."
        return f"Pointing at the {found.label}, {side(found.yaw)}."
