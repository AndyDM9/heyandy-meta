"""What the TV shows: Andy's words, who answered, and the picture a thing was found in.

The picture lives only here, in memory, and is dropped after two minutes. Nothing on this page is saved.
"""
import base64
import threading
import time
from dataclasses import dataclass

from ..finder.search import Found

PICTURE_SECONDS = 120
HELP_SECONDS = 60
DRAWING_SECONDS = 10 * 60


@dataclass
class _Picture:
    jpeg: bytes
    found: Found
    words: str
    until: float


class ScreenState:
    def __init__(self, clock=time.monotonic):
        self._clock, self._lock = clock, threading.Lock()
        self.caption = ""
        self.source, self.reason = "", ""
        self.online = True
        self._picture: _Picture | None = None
        self.sources: list[tuple[str, str]] = []  # (title, url) under an answer
        self.steps: list[str] = []  # the plan as it happens: "look: right, far right"
        self.memory: list[str] | None = None  # shown while "what do you remember?" is answered
        self._timer: tuple[float, float | None] | None = None  # (started, stopped)
        self.models: dict[str, list] = {}  # this turn's Meta models: name -> [where, times used]
        self.state, self.head = "Waiting", ""  # the pill: what Andy is doing, and what its head is turned to
        self.looking_for = ""  # "your cup", while a search runs and after
        self.next_reminder: tuple[str, float] | None = None  # (the person's words, when), epoch seconds
        self.watching: list[str] = []  # what Andy keeps an eye on, and where it last saw each
        self.watching_map: list[dict] = []  # the same as directions, for the TV's map
        self._help_until = 0.0
        self.staged = False  # a staged scene: camera pictures go to the Model API, and the TV says so
        self._drawing: tuple[bytes, str, str, float] | None = None  # (WebP, what was asked, where it's saved, until)
        self.drawings = 0  # a version for the page, so it fetches each new picture once

    def doing(self, state: str, head: str = "") -> None:
        with self._lock:
            self.state, self.head = state, head

    def looking(self, thing: str) -> None:
        with self._lock:
            self.looking_for = thing

    def reminder_next(self, text: str | None, at: float = 0.0) -> None:
        with self._lock:
            self.next_reminder = (text, at) if text else None

    def keeping(self, lines: list[str], where: list[dict] | None = None) -> None:
        with self._lock:
            self.watching, self.watching_map = list(lines), list(where or [])

    def drawn(self, image: bytes, prompt: str, saved: str) -> None:
        with self._lock:
            self._picture, self.sources, self.steps, self.memory, self._timer, self.looking_for = None, [], [], None, None, ""
            self._drawing = (image, prompt, saved, self._clock() + DRAWING_SECONDS)
            self.drawings += 1

    def drawing_bytes(self) -> bytes | None:
        with self._lock:
            return self._drawing[0] if self._drawing else None

    def show_help(self) -> None:
        with self._lock:
            self._help_until = self._clock() + HELP_SECONDS

    def new_turn(self) -> None:
        with self._lock:
            self.models = {}

    def used(self, name: str, where: str = "device", times: int = 1) -> None:
        """A model worked on this turn: "device" (this computer) or "cloud" (words only)."""
        if times <= 0:
            return
        with self._lock:
            self.models.setdefault(name, [where, 0])[1] += times

    def said(self, text: str, source: str = "", reason: str = "") -> None:
        with self._lock:
            self.caption, self.source, self.reason = text, source, reason

    def found(self, found: Found, words: str) -> None:
        if not found.frame.image:  # the pretend room has no camera: words only
            return
        with self._lock:
            self._picture = _Picture(found.frame.image, found, words, self._clock() + PICTURE_SECONDS)

    def clear(self) -> None:
        with self._lock:
            self._picture, self.sources, self.steps, self.memory, self._timer = None, [], [], None, None
            self.looking_for, self._help_until, self._drawing = "", 0.0, None

    def answered(self, text: str, sources: list[tuple[str, str]], source: str = "cloud", reason: str = "") -> None:
        with self._lock:
            self.caption, self.source, self.reason, self.sources = text, source, reason, list(sources)[:3]

    def step(self, line: str) -> None:
        with self._lock:
            self.steps = (self.steps + [line])[-6:]

    def remember_list(self, lines: list[str]) -> None:
        with self._lock:
            self.memory = list(lines)

    def timer_start(self) -> None:
        with self._lock:
            self._timer, self.steps = (self._clock(), None), []

    def timer_stop(self) -> None:
        with self._lock:
            if self._timer and self._timer[1] is None:
                self._timer = (self._timer[0], self._clock())

    def snapshot(self) -> dict:
        with self._lock:
            if self._picture and self._clock() >= self._picture.until:
                self._picture = None
            out = {"caption": self.caption, "source": self.source, "reason": self.reason, "online": self.online,
                   "picture": None, "sources": [{"title": a, "url": b} for a, b in self.sources],
                   "steps": list(self.steps), "memory": self.memory, "seconds": None, "running": False,
                   "models": [{"name": n, "where": w, "times": t} for n, (w, t) in self.models.items()],
                   "state": self.state, "head": self.head, "looking_for": self.looking_for,
                   "next": {"text": self.next_reminder[0], "at": self.next_reminder[1]} if self.next_reminder else None,
                   "watching": list(self.watching), "map": list(self.watching_map),
                   "help": self._clock() < self._help_until,
                   "staged": self.staged, "drawing": None}
            if self._drawing and self._clock() >= self._drawing[3]:
                self._drawing = None
            if self._drawing:
                out["drawing"] = {"v": self.drawings, "prompt": self._drawing[1], "saved": self._drawing[2]}
            if self._timer:
                start, stop = self._timer
                out["seconds"] = round((stop if stop is not None else self._clock()) - start, 1)
                out["running"] = stop is None
            p = self._picture
            if p:
                f, m = p.found, p.found.mask
                out["picture"] = {
                    "src": "data:image/jpeg;base64," + base64.b64encode(p.jpeg).decode(),
                    "width": f.frame.width, "height": f.frame.height,
                    "label": f.label, "words": p.words,
                    "outline": m.outline, "box": list(m.box), "scale": list(m.outline_scale),
                    "seconds_left": round(p.until - self._clock()),
                }
            return out
