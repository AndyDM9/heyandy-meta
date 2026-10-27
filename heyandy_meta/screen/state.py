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

    def said(self, text: str, source: str = "", reason: str = "") -> None:
        with self._lock:
            self.caption, self.source, self.reason = text, source, reason

    def found(self, found: Found, words: str) -> None:
        with self._lock:
            self._picture = _Picture(found.frame.image, found, words, self._clock() + PICTURE_SECONDS)

    def clear(self) -> None:
        with self._lock:
            self._picture = None

    def snapshot(self) -> dict:
        with self._lock:
            if self._picture and self._clock() >= self._picture.until:
                self._picture = None
            out = {"caption": self.caption, "source": self.source, "reason": self.reason, "online": self.online,
                   "picture": None}
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
