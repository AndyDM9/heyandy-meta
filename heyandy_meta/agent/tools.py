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
# Colours are for compare, which checks them in the pictures on this computer: SAM 3.1 looks for the thing itself, so
# "blue mug" finds every mug and compare picks the blue one, rather than a look that misses a mug in odd light.
COLOURS = {"red", "blue", "green", "yellow", "black", "white", "grey", "gray", "brown", "pink", "purple", "orange",
           "silver", "gold", "golden", "beige", "navy", "dark", "light"}
AROUND = {"you", "your", "me", "my", "left", "right", "behind", "front", "here", "there"}  # where, not which one
WHERE = re.compile(r"\s+(?:in|on|by|near|next to|under|behind|beside|at|from|with|in front of)\s.*$")  # "mug next to the laptop"
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
    looked: set = field(default_factory=set)  # (object, view) already searched
    confirmed: dict[str, Found] = field(default_factory=dict)
    pointed: Found | None = None
    described: str = ""  # which one the person meant ("red", "next to the laptop"), taken out of the object for compare
    compared: bool = False
    auto_point: bool = True  # a confirmed closer look points at once: one model call fewer
    on_tool: object = None  # told True before a tool runs and False after (the body holds still while it looks)
    max_looks: int = 10  # frames a search may take; the simulated scorecard's absent rooms took 22 without it

    def __post_init__(self):
        self._start = self.finder.looks

    def _looks_left(self) -> int:
        return self.max_looks - (self.finder.looks - self._start)

    def specs(self) -> list[dict]:
        """The tools to offer: recall only when something is being watched."""
        watching = bool(self.places and self.places.watching())
        return [s for s in SPECS if watching or s["function"]["name"] != "recall"]

    def call(self, name: str, args: dict) -> str:
        handler = {"recall": self._recall, "look": self._look, "look_closer": self._closer, "compare": self._compare,
                   "point": self._point}.get(name)
        if handler is None:
            return f"refused: there is no tool called {name!r}"
        if isinstance(args, dict):  # "place 2" for "2", as models sometimes write it
            args = {k: _place(v) if k == "place" else [_place(x) for x in v] if k == "places" and isinstance(v, list)
                    else v for k, v in args.items()}
        if self.on_tool:
            self.on_tool(True)
        try:
            return handler(**args)
        except TypeError:
            return f"refused: wrong arguments for {name}"
        finally:
            if self.on_tool:
                self.on_tool(False)

    def meant(self, words: str) -> None:
        """What the person asked for ("the red cup"): its colour or place is checked before any point, whatever object
        the planner names later (on the robot, 2026-10-31, Glimmer looked for plain "cup" and the colour was lost)."""
        self._object(words)

    def _object(self, obj) -> str | None:
        if not isinstance(obj, str) or not OBJECT.match(obj.strip()):
            return None
        text = obj.strip().lower()
        where = WHERE.search(text)
        words = WHERE.sub("", text).split()  # where it is is for compare too
        plain = [w for w in words if w not in COLOURS] or words
        seen = [w for w in words if w not in plain]  # what a picture can show: a colour, what it's next to
        if where and not set(where.group().split()) & AROUND:
            seen.append(where.group().strip())
        if seen:
            self.described = " ".join(seen)
        return " ".join(plain)

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
        new = [v for v in dict.fromkeys(views) if (obj, v) not in self.looked]
        if not new:  # looking again costs moves and finds the same: say what's known instead
            return (f"You've already looked for the {obj} in {', '.join(views)}. Places so far: "
                    f"{self._places_so_far()}. Use look_closer or compare on them, or try other views.")
        if self._looks_left() < 1:
            return "refused: you've looked enough for one search. Stop, and tell the person you couldn't find it."
        new = new[: self._looks_left()]
        self.looked.update((obj, v) for v in new)
        found = self.finder.scan(obj, [VIEWS[v] for v in new])
        if not found:
            return f"No {obj} seen in: {', '.join(new)}."
        lines = []
        for s in found[:5]:
            pid = str(len(self.candidates) + 1)
            self.candidates[pid] = (s.yaw, s.pitch)
            lines.append(f"place {pid}: {side(s.yaw)}, confidence {s.score:.2f}, seen in {s.views} view(s)")
        out = "Possible " + obj + ": " + "; ".join(lines)
        if obj != object.strip().lower():  # the person said which one: the colour is checked by compare
            out += (f". I looked for any {obj}; use compare with the person's description to tell them apart"
                    if len(found) > 1 else f". I looked for any {obj}; check it's the right one with look_closer")
        return out

    def _places_so_far(self) -> str:
        return "; ".join(f"place {p}: {side(yaw)}" for p, (yaw, _) in self.candidates.items()) or "none"

    def _closer(self, object, place) -> str:
        obj = self._object(object)
        if obj is None:
            return "refused: the object must be a short plain noun phrase"
        if place not in self.candidates:
            return f"refused: no place {place!r}; places so far: {list(self.candidates) or 'none'}"
        if self._looks_left() < 1:
            return "refused: you've looked enough for one search. Stop, and tell the person you couldn't find it."
        several = len([p for p in self.candidates if p != "remembered"]) > 1
        if self.described and several and not self.compared:  # the person said which one: never point at a guess
            return (f"refused: there is more than one {obj}; use compare with the person's description "
                    f"('{self.described}') on places {', '.join(p for p in self.candidates if p != 'remembered')} first")
        found = self.finder.confirm(obj, *self.candidates[place])
        if found is None:
            return f"Looked closer at place {place}: {self.finder.why or 'not there'}."
        if self.described and not self.compared and self.judge is not None:  # only one: is it the one they meant?
            if self.judge.pick([(found.frame, found.mask)], f"the {obj} that is {self.described}") is None:
                return (f"Looked closer at place {place}: a {obj}, but it doesn't look like '{self.described}'. "
                        "Look in other views, or tell the person what you found.")
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
            self.described = ""  # nothing to compare with: look_closer may go ahead
            return "I can't compare pictures right now; look_closer at the likeliest place instead."
        self.compared = True
        if self._looks_left() < 1:
            return "refused: you've looked enough for one search. Stop, and tell the person you couldn't find it."
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
        if i is not None and len(seen) > 1:  # shown two of one blue cup and asked for red, Glimmer still picks one
            meant = " ".join(w for w in description.strip().split() if w.lower() not in obj.split())
            win = self.confirmed[seen[i]]
            if self.judge.pick([(win.frame, win.mask)], f"the {obj} that is {meant or description.strip()}") is None:
                i = None
        for p in seen:
            if i is None or p != seen[i]:
                self.confirmed.pop(p)  # only the one that fits may be pointed at
        if i is None:
            return f"Compared places {', '.join(seen)}: none looks like '{description.strip()}'. Ask the person."
        if self.auto_point:  # the one that fits is confirmed: point at once, one model call fewer
            return f"Place {seen[i]} fits '{description.strip()}'. " + self._point(seen[i])
        return f"Place {seen[i]} fits '{description.strip()}' and is confirmed, {side(self.confirmed[seen[i]].yaw)}."

    def _point(self, place) -> str:
        found = self.confirmed.get(place)
        if found is None:
            return f"refused: place {place!r} isn't confirmed; use look_closer first"
        self.pointed = self.finder.point(found)
        if self.places:
            self.places.saw(found.label, found.yaw, found.pitch, how="found")
        if not found.reachable:
            return f"I can't turn far enough to point; it's {side(found.yaw)}. Tell the person."
        return f"Pointing at the {found.label}, {side(found.yaw)}."


def _place(p):
    return re.sub(r"^\s*place\s+", "", p, flags=re.I).strip() if isinstance(p, str) else p
