"""A pretend room for tests and demos without the robot: objects at known directions, and a body that looks at them.

The room's camera is the same pinhole as the real one, so a test can check that the finder points where an object
really is. Frames carry no picture; the room's own segmenter reads the head's direction from them instead.
"""
import math
from dataclasses import dataclass, field

from ..finder.geometry import LITE, Camera
from ..models.common import Mask
from .body import Frame, Reach


@dataclass
class Thing:
    label: str
    yaw: float
    pitch: float
    size_px: int = 60  # how wide it looks at 1080p
    score: float = 0.9
    on_screen: bool = False  # a picture of the thing on a TV or in a photo
    looks: str = ""  # what tells it apart from others like it, e.g. "blue, next to the laptop"


@dataclass
class Room:
    things: list[Thing] = field(default_factory=list)
    cam: Camera = LITE

    def where_in_frame(self, thing: Thing, yaw: float, pitch: float) -> tuple[float, float] | None:
        dyaw, dpitch = math.radians(thing.yaw - yaw), math.radians(thing.pitch - pitch)
        if abs(dyaw) >= math.pi / 2 or abs(dpitch) >= math.pi / 2:
            return None
        x = self.cam.cx - self.cam.fx * math.tan(dyaw)
        y = self.cam.cy + self.cam.fx * math.tan(dpitch)
        h = thing.size_px / 2
        if h <= x < self.cam.width - h and h <= y < self.cam.height - h:
            return x, y
        return None


class SimBody:
    def __init__(self, room: Room, reach: Reach = Reach()):
        self.room, self.reach = room, reach
        self.yaw = self.pitch = 0.0
        self.log: list[tuple] = []

    def look(self, yaw: float, pitch: float, precise: bool = True) -> None:
        self.yaw, self.pitch = self.reach.clamp(yaw, pitch)
        self.log.append(("look", round(self.yaw, 2), round(self.pitch, 2)))

    def capture(self) -> Frame:
        self.log.append(("capture",))
        return Frame(b"", self.room.cam.width, self.room.cam.height, self.yaw, self.pitch)

    def point(self, yaw: float, pitch: float) -> None:
        self.look(yaw, pitch)
        self.log.append(("point", round(self.yaw, 2), round(self.pitch, 2)))

    def say(self, text: str) -> None:
        self.log.append(("say", text))


class SimSegmenter:
    """Answers like SAM 3.1 would, from the room's ground truth."""

    def __init__(self, room: Room):
        self.room = room
        self.calls = 0

    def find(self, frame: Frame, query: str) -> list[Mask]:
        self.calls += 1
        masks = []
        for t in self.room.things:
            if t.label != query:
                continue
            at = self.room.where_in_frame(t, frame.yaw, frame.pitch)
            if at is None:
                continue
            h = t.size_px // 2
            box = (int(at[0]) - h, int(at[1]) - h, int(at[0]) + h, int(at[1]) + h)
            masks.append(Mask(query, box, t.score, center=at, area=t.size_px ** 2))
        return masks


    def embed(self, frame: Frame, masks: list[Mask]) -> list[list[float]]:
        """Like DINOv2 would: things that look the same (same ``looks``) get the same vector, others a different one."""
        out = []
        for m in masks:
            t = next((t for t in self.room.things if t.label == m.label and (at := self.room.where_in_frame(
                t, frame.yaw, frame.pitch)) and abs(at[0] - m.center[0]) < 2 and abs(at[1] - m.center[1]) < 2), None)
            k = sum(map(ord, t.looks if t else "")) % 8
            out.append([1.0 if i == k else 0.1 for i in range(8)])
        return out


class SimJudge:
    """Answers like Glimmer's picture checks would, from the room's ground truth."""

    def __init__(self, room: Room):
        self.room = room
        self.calls = 0

    def _thing(self, frame: Frame, mask: Mask) -> Thing | None:
        for t in self.room.things:
            at = self.room.where_in_frame(t, frame.yaw, frame.pitch)
            if t.label == mask.label and at and abs(at[0] - mask.center[0]) < 2 and abs(at[1] - mask.center[1]) < 2:
                return t
        return None

    def describe(self, frame: Frame, where: str = "", box=None) -> str | None:
        self.calls += 1
        seen = [t.label for t in self.room.things if self.room.where_in_frame(t, frame.yaw, frame.pitch)]
        return ("I see " + " and ".join(f"a {x}" for x in seen) + ".") if seen else "I don't see anything in particular."

    def where_near(self, frame: Frame, mask: Mask) -> str | None:
        self.calls += 1
        t = self._thing(frame, mask)
        others = [o for o in self.room.things if t and o is not t and abs(o.yaw - t.yaw) < 20 and not o.on_screen]
        return f"next to the {others[0].label}" if others else "on its own"

    def real(self, frame: Frame, mask: Mask) -> bool:
        self.calls += 1
        t = self._thing(frame, mask)
        return not (t and t.on_screen)

    def pick(self, found: list[tuple[Frame, Mask]], description: str) -> int | None:
        """Like Glimmer looking at the crops: the words of the description, and "not the one on the TV"."""
        self.calls += 1
        words = set(description.lower().replace(",", " ").split())
        real_only = bool(words & {"tv", "screen", "picture", "photo", "television"}) and bool(words & {"not", "real"})
        overlap = []
        for frame, mask in found:
            t = self._thing(frame, mask)
            score = len(words & set(t.looks.lower().replace(",", " ").split())) if t else 0
            if real_only and t:
                score += 0 if t.on_screen else 1
            overlap.append(score)
        best = max(range(len(found)), key=overlap.__getitem__, default=None)
        return best if best is not None and overlap[best] > 0 else None
