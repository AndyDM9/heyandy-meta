"""What the TV shows: Andy's words, who answered, and the picture a thing was found in.

The picture lives only here, in memory, and is dropped after two minutes. Nothing on this page is saved.
"""
import base64
import threading
import time
from dataclasses import dataclass

from ..finder.search import Found

PICTURE_SECONDS = 120


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
                   "models": [{"name": n, "where": w, "times": t} for n, (w, t) in self.models.items()]}
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
