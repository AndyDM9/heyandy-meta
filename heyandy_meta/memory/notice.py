"""Noticing a thing put down or picked up, while Andy keeps an eye on things: V-JEPA 2, Meta's video world model.

Between turns, Andy watches a few seconds at a time. Where something moved in the picture (frame differences, on the
processor), V-JEPA 2 on this computer judges that part of the clip: was a thing put down, or picked up? If so, SAM 3.1
looks at the last frame for the things being watched, and a watched thing found where the movement was gets that
place in Andy's memory, as when it's found. Nothing moved, or the whole picture moved (Andy's own head): nothing is
asked. Only while the person has asked Andy to keep an eye on something; the frames are dropped after each clip.
"""
import io
import time
from dataclasses import dataclass, field

from PIL import Image, ImageChops

from ..finder.geometry import Camera, pixel_to_angles

SMALL = (160, 90)


def moved(images: list[bytes], changed: int = 28, least: float = 0.002, most: float = 0.3):
    """Where the picture changed over a clip, as a box in the frame's pixels, and the share of it that changed.
    None for the box when nothing moved, or when so much did that it was the camera (the head) moving."""
    if len(images) < 2:
        return None, 0.0
    first = Image.open(io.BytesIO(images[0]))
    small = [Image.open(io.BytesIO(b)).convert("L").resize(SMALL) for b in images]
    seen = Image.new("L", SMALL, 0)
    for a, b in zip(small, small[1:]):
        seen = ImageChops.lighter(seen, ImageChops.difference(a, b).point(lambda v: 255 if v > changed else 0))
    share = seen.histogram()[255] / (SMALL[0] * SMALL[1])
    box = seen.getbbox()
    if box is None or not least <= share <= most:
        return None, share
    sx, sy = first.width / SMALL[0], first.height / SMALL[1]
    return (box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy), share


@dataclass
class Noticer:
    body: object  # grab(): the next camera frame, without moving
    seer: object  # SAM 3.1 on this computer: action() (V-JEPA 2) and find_many()
    places: object  # Andy's memory of where watched things were seen
    cam: Camera = field(default_factory=Camera)
    frames: int = 16
    every_s: float = 0.25  # 16 frames over 4 s, about the pace of V-JEPA 2's training clips
    sure: float = 0.5
    clock: object = time.time
    sleep: object = time.sleep
    last: dict | None = None  # the last clip's verdict, for the TV and the tests

    def watch_once(self, cancelled=lambda: False) -> dict | None:
        """One clip. Returns what was noticed ({"kind": "put" or "taken", "things": [...]}), or None. ``cancelled`` is
        asked between frames and before each model and the memory: a turn starting ends the clip, with no change."""
        watching = self.places.watching()
        if not watching:
            return None
        clip = []
        for _ in range(self.frames):
            if cancelled():
                return None
            clip.append(self.body.grab())
            self.sleep(self.every_s)
        box, share = moved([f.image for f in clip])
        if box is None or cancelled():
            self.last = {"moved": round(share, 4)}
            return None
        verdict = self.seer.action(clip, box)
        self.last = {"moved": round(share, 4), **verdict}
        kind = "put" if verdict["put"] >= self.sure else "taken" if verdict["taken"] >= self.sure else None
        if kind is None or cancelled():
            return None
        end = clip[-1]
        del clip
        cam = self.cam.scaled(end.width, end.height)
        l, t, r, b = box
        pad = max(r - l, b - t) * 0.25
        things, where = [], {}
        found = self.seer.find_many(end, watching)
        if cancelled():
            return None
        for label, masks in found.items():
            here = [m for m in masks if (m.score or 0.0) >= 0.5
                    and l - pad <= m.center[0] <= r + pad and t - pad <= m.center[1] <= b + pad]
            if kind == "put" and here:
                best = max(here, key=lambda m: m.score or 0.0)
                yaw, pitch = pixel_to_angles(*best.center, end.yaw, end.pitch, cam)
                self.places.saw(label, yaw, pitch, when=self.clock(), how="noticed")
                things.append(label)
                where[label] = best
            elif kind == "taken" and not here and self._last_seen_there(label, end, cam, box):
                getattr(self.places, "picked_up", lambda *a, **k: None)(label, when=self.clock())
                things.append(label)
        # the last frame and each put-down thing's mask go back once, so its new place can be put in words; then dropped
        return {"kind": kind, "things": things, "frame": end, "masks": where, **verdict} if things else None

    def _last_seen_there(self, label: str, frame, cam: Camera, box) -> bool:
        """Was this watched thing last seen where the movement was? Then picking it up is what moved."""
        last = self.places.last_seen(label, now=self.clock())
        if not last:
            return False
        l, t, r, b = box
        y0, p0 = pixel_to_angles(l, t, frame.yaw, frame.pitch, cam)
        y1, p1 = pixel_to_angles(r, b, frame.yaw, frame.pitch, cam)
        return min(y0, y1) - 3 <= last[0] <= max(y0, y1) + 3 and min(p0, p1) - 3 <= last[1] <= max(p0, p1) + 3
