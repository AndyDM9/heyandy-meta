"""From a pixel in a view to where the head should look, and merging sightings.

A pinhole camera at the head's pivot, square pixels, no lens distortion, and the pixel's ray turned by the view's
pitch and then its yaw. Yaw is positive to the left, pitch positive down.

Measured on our Lite (2026-11-01, evening): the keys, the cup and the glasses seen from 36 head directions (90
sightings), each thing's direction compared across views. Adding the pixel's two angles to the view's, as this did
before, is right only on the frame's middle row and column: with the head tilted down, a thing at the side of the frame
sits higher than the middle row says. Its sightings disagreed by a median 1.6 to 1.9 degrees (at the frame's sides 3.2,
nine in ten within 6.2); turned properly, 0.9 to 1.1 (at the sides 1.6, nine in ten within 2.8). Pollen's published lens
calibration, with its 12 distortion terms, did worse than this plain lens (1.4 to 2.1), and fitting the focal length
on two of the things and testing on the third gave 1050 to 1090: the 1054 below stands.
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


def _axes(view_yaw: float, view_pitch: float):
    """The camera's forward, right and down directions in the room (x ahead, y to the left, z up)."""
    ps, th = math.radians(view_yaw), math.radians(view_pitch)
    forward = (math.cos(th) * math.cos(ps), math.cos(th) * math.sin(ps), -math.sin(th))
    right = (math.sin(ps), -math.cos(ps), 0.0)
    down = (-math.sin(th) * math.cos(ps), -math.sin(th) * math.sin(ps), -math.cos(th))
    return forward, right, down


def pixel_to_angles(x: float, y: float, view_yaw: float, view_pitch: float, cam: Camera = LITE) -> tuple[float, float]:
    """Head yaw and pitch, in degrees, that put pixel (x, y) of this view at the centre: the pixel's ray in the room."""
    forward, right, down = _axes(view_yaw, view_pitch)
    a, b = (x - cam.cx) / cam.fx, (y - cam.cy) / cam.fx
    w = [forward[i] + a * right[i] + b * down[i] for i in range(3)]
    return math.degrees(math.atan2(w[1], w[0])), math.degrees(math.atan2(-w[2], math.hypot(w[0], w[1])))


def angles_to_pixel(yaw: float, pitch: float, view_yaw: float, view_pitch: float,
                    cam: Camera = LITE) -> tuple[float, float] | None:
    """Where a direction in the room falls in this view, in pixels; None if it's behind the camera."""
    forward, right, down = _axes(view_yaw, view_pitch)
    ps, th = math.radians(yaw), math.radians(pitch)
    w = (math.cos(th) * math.cos(ps), math.cos(th) * math.sin(ps), -math.sin(th))
    ahead = sum(w[i] * forward[i] for i in range(3))
    if ahead <= 1e-6:
        return None
    return (cam.cx + cam.fx * sum(w[i] * right[i] for i in range(3)) / ahead,
            cam.cy + cam.fx * sum(w[i] * down[i] for i in range(3)) / ahead)


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
