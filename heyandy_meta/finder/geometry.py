"""From a pixel in a view to where the head should look, and merging sightings.

A pinhole camera at the head's pivot, square pixels, no lens distortion: good to a degree or two near the
centre of the frame, worse at the edges. Yaw is positive to the left, pitch positive down.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Camera:
    width: int = 1920
    height: int = 1080
    # Measured on our Lite (2026-10-31): a watch, a cup and glasses each centred, then seen from 27 head angles up to
    # 42 degrees off; the published 1116 put things up to 4.7 degrees out near the edges, 1054 fits all 80 sightings
    # (the centre as published). Pollen's published calibration: fx 1116, cx 953, cy 542, at 1920x1080.
    fx: float = 1054.0
    cx: float = 953.0
    cy: float = 542.0

    def scaled(self, width: int, height: int) -> "Camera":
        """The same camera at another frame size."""
        s = width / self.width
        return Camera(width, height, self.fx * s, self.cx * s, self.cy * (height / self.height))


LITE = Camera()


def pixel_to_angles(x: float, y: float, view_yaw: float, view_pitch: float, cam: Camera = LITE) -> tuple[float, float]:
    """Head yaw and pitch, in degrees, that put pixel (x, y) of this view at the centre."""
    yaw = view_yaw + math.degrees(math.atan2(cam.cx - x, cam.fx))
    pitch = view_pitch + math.degrees(math.atan2(y - cam.cy, cam.fx))
    return yaw, pitch


@dataclass
class Sighting:
    yaw: float
    pitch: float
    score: float  # 0-1; a missing SAM score counts as 0.5
    views: int = 1  # how many views saw it here


def merge(sightings: list[Sighting], within_deg: float = 6.0) -> list[Sighting]:
    """Join sightings of one place seen from overlapping views; strongest first."""
    places: list[Sighting] = []
    for s in sorted(sightings, key=lambda s: -s.score):
        near = next((p for p in places if math.hypot(p.yaw - s.yaw, p.pitch - s.pitch) <= within_deg), None)
        if near is None:
            places.append(Sighting(s.yaw, s.pitch, s.score))
            continue
        n = near.views
        near.yaw = (near.yaw * n + s.yaw) / (n + 1)
        near.pitch = (near.pitch * n + s.pitch) / (n + 1)
        near.views = n + 1
        near.score = max(near.score, s.score)
    return sorted(places, key=lambda p: (-p.views, -p.score))
