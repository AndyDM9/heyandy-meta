"""Turn to look at the person. SAM 3.1 finds "person" in view; nothing about who it is is kept or asked.

Andy looks where it is already facing first, then the room's views, and aims a little below the top of the person's
mask, where a face usually is. It forgets the direction as soon as it has turned.
"""
from ..finder.geometry import pixel_to_angles
from ..finder.search import VIEWS, Segmenter
from ..robot.body import Body

FACE_FROM_TOP = 0.18  # a face sits about this far down a standing or seated person's mask


def face_person(body: Body, segmenter: Segmenter, views=VIEWS, min_score: float = 0.4) -> tuple[float, float] | None:
    """Turn to the nearest person in view and return the direction, or None if nobody is there."""
    here = (getattr(body, "yaw", 0.0), getattr(body, "pitch", 0.0))
    for yaw, pitch in (here, *[v for v in views if v != here]):
        if not body.reach.allows(yaw, pitch):
            continue
        body.look(yaw, pitch)
        frame = body.capture()
        people = [m for m in segmenter.find(frame, "person") if m.score is None or m.score >= min_score]
        if not people:
            continue
        nearest = max(people, key=lambda m: m.area)  # the biggest mask is usually the closest person
        left, top, right, bottom = nearest.box
        x, y = (left + right) / 2, top + FACE_FROM_TOP * (bottom - top)
        direction = pixel_to_angles(x, y, frame.yaw, frame.pitch)
        body.look(*direction)
        return direction
    return None
