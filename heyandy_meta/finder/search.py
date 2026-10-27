"""Find a thing in the room: recall where it was, else sweep four views, then look closer, check, and point.

Each step is a direction for the body and a frame for SAM 3.1. A sighting only becomes a point after a second,
centred look confirms it; one look is never enough. The frame it was confirmed in is returned in memory, for the
TV, and never saved.
"""
import math
from dataclasses import dataclass
from typing import Callable, Protocol

from ..models.common import Mask
from ..robot.body import Body, Frame
from .geometry import LITE, Camera, Sighting, merge, pixel_to_angles
from .names import also

VIEWS = ((18.0, 15.0), (-18.0, 15.0), (55.0, 15.0), (-55.0, 15.0))  # yaw, pitch; the middle first; about 190 degrees
BEHIND = ((110.0, 15.0), (-110.0, 15.0))  # turning the base; only when the front sweep finds nothing


class Segmenter(Protocol):
    def find(self, frame: Frame, query: str) -> list[Mask]: ...


@dataclass
class Found:
    label: str
    yaw: float
    pitch: float
    score: float
    frame: Frame  # the close-up it was confirmed in
    mask: Mask
    looks: int  # frames read to get here
    remembered: bool = False  # found at the place it was last seen
    reachable: bool = True  # False: the body can't point all the way, so say where instead


@dataclass
class Finder:
    body: Body
    segmenter: Segmenter
    cam: Camera = LITE
    views: tuple = VIEWS
    behind: tuple = BEHIND
    min_score: float = 0.3
    closer_looks: int = 2
    sure: float = 0.75  # a sighting this confident gets its closer look at once, before the sweep goes on
    confirm_within_px: float = 0.15  # a close-up's mask must be this near the centre (fraction of frame width)
    check: Callable[[Frame, Mask], bool] | None = None  # optional second opinion, e.g. "is this on a screen?"
    why: str = ""  # why the last closer look came back empty, in words for the plan and the TV
    on_look: Callable[[float, float], None] | None = None  # told each direction as the head turns (the TV's progress)

    def find(self, label: str, last_seen: tuple[float, float] | None = None) -> Found | None:
        """The fixed search: the remembered place, then a sweep, then behind. A confident sighting is checked as soon
        as it's seen; otherwise the likeliest places get a closer look after the sweep, up to ``closer_looks``."""
        self.looks = 0
        if last_seen is not None:
            found = self.confirm(label, *last_seen)
            if found:
                found.remembered = True
                return self.point(found)
        tried: list[Sighting] = []

        def try_(place: Sighting) -> Found | None:
            if len(tried) >= self.closer_looks + 2 or any(
                    math.hypot(place.yaw - t.yaw, place.pitch - t.pitch) <= 6.0 for t in tried):
                return None  # a place already looked at closely, or enough closer looks for one search
            tried.append(place)
            return self.confirm(label, place.yaw, place.pitch)

        for views in (self.views, self.behind):
            sightings: list[Sighting] = []
            for view in views:
                sightings += self._sightings(label, *view)
                for place in merge(sightings):
                    if place.score >= self.sure:
                        found = try_(place)
                        if found:
                            return self.point(found)
            for place in merge(sightings)[: self.closer_looks]:
                found = try_(place)
                if found:
                    return self.point(found)
        return None

    def scan(self, label: str, views) -> list[Sighting]:
        """Look in each view and return the places where the thing might be, likeliest first."""
        sightings = []
        for yaw, pitch in views:
            sightings += self._sightings(label, yaw, pitch)
        return merge(sightings)

    def _sightings(self, label: str, yaw: float, pitch: float) -> list[Sighting]:
        if not self.body.reach.allows(yaw, pitch):
            return []
        frame = self._look(yaw, pitch, precise=False)  # the frame says where it was taken; no need to be exact
        return [Sighting(*pixel_to_angles(*m.center, frame.yaw, frame.pitch, self._cam(frame)),
                         m.score if m.score is not None else 0.5) for m in self._masks(frame, label)]

    def confirm(self, label: str, yaw: float, pitch: float) -> Found | None:
        """Look straight at a place; it counts only if the thing is near the centre of that frame."""
        self.why = ""
        frame = self._look(yaw, pitch)
        cam = self._cam(frame)
        near = [m for m in self._masks(frame, label)
                if abs(m.center[0] - cam.cx) <= self.confirm_within_px * frame.width
                and abs(m.center[1] - cam.cy) <= self.confirm_within_px * frame.width]
        if not near:
            self.why = "not there"
            return None
        best = min(near, key=lambda m: (m.center[0] - cam.cx) ** 2 + (m.center[1] - cam.cy) ** 2)
        if self.check and not self.check(frame, best):
            self.why = "only a picture of one, on a screen or in a photo"
            return None
        y, p = pixel_to_angles(*best.center, frame.yaw, frame.pitch, cam)
        return Found(label, y, p, best.score if best.score is not None else 0.5, frame, best, self.looks)

    def point(self, found: Found) -> Found:
        found.reachable = self.body.reach.allows(found.yaw, found.pitch)
        self.body.point(found.yaw, found.pitch)  # the body clamps an unreachable direction to its limit
        return found

    looks: int = 0

    def _look(self, yaw: float, pitch: float, precise: bool = True) -> Frame:
        if self.on_look:
            self.on_look(yaw, pitch)
        self.body.look(yaw, pitch, precise)
        self.looks += 1
        return self.body.capture()

    def _masks(self, frame: Frame, label: str) -> list[Mask]:
        """SAM 3.1 asked for the thing and a couple of close names ("cup": also "mug"), in one request if it can."""
        many, names = getattr(self.segmenter, "find_many", None), also(label)
        found = [m for ms in many(frame, names).values() for m in ms] if many and len(names) > 1 \
            else self.segmenter.find(frame, label)
        for m in found:
            m.label = label
        return [m for m in _dedupe(found) if m.score is None or m.score >= self.min_score]

    def _cam(self, frame: Frame) -> Camera:
        if (frame.width, frame.height) == (self.cam.width, self.cam.height):
            return self.cam
        return self.cam.scaled(frame.width, frame.height)


def _dedupe(masks: list[Mask]) -> list[Mask]:
    """The same thing found under two names: keep the more confident mask."""
    out: list[Mask] = []
    for m in sorted(masks, key=lambda m: -(m.score if m.score is not None else 0.5)):
        if not any(abs(m.center[0] - o.center[0]) < 12 and abs(m.center[1] - o.center[1]) < 12 for o in out):
            out.append(m)
    return out
