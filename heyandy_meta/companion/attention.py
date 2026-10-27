"""Turn to look at the person. SAM 3.1 finds "person" in view; nothing about who it is is kept or asked.

Andy looks where it is already facing first, then the room's views, and aims a little below the top of the person's
mask, where a face usually is. It forgets the direction as soon as it has turned.
"""
from ..finder.geometry import pixel_to_angles
from ..finder.search import VIEWS, Segmenter
from ..robot.body import Body

FACE_FROM_TOP = 0.18  # a face sits about this far down a standing or seated person's mask
# Looking up at a face from a desk tips the head far back, which reads as staring at the ceiling, not at the person
# (founder, 2026-10-27). Eye contact reads well with the head only slightly raised: take part of an upward look, capped.
LOOK_UP_SHARE, LOOK_UP_CAP = 0.6, -12.0


def soften_look_up(pitch: float) -> float:
    """Pitch is positive down; an upward look is eased and capped."""
    return pitch if pitch >= 0 else max(LOOK_UP_CAP, LOOK_UP_SHARE * pitch)


def face_person(body: Body, segmenter: Segmenter, views=VIEWS, min_score: float = 0.4) -> tuple[float, float] | None:
    """Turn to the nearest person in view and return the direction, or None if nobody is there."""
    here = (getattr(body, "yaw", 0.0), getattr(body, "pitch", 0.0))
    for yaw, pitch in (here, *[v for v in views if v != here]):
        if not body.reach.allows(yaw, pitch):
            continue
        body.look(yaw, pitch, precise=False)
        frame = body.capture()
        people = [m for m in segmenter.find(frame, "person") if m.score is None or m.score >= min_score]
        if not people:
            continue
        nearest = max(people, key=lambda m: m.area)  # the biggest mask is usually the closest person
        left, top, right, bottom = nearest.box
        x, y = (left + right) / 2, top + FACE_FROM_TOP * (bottom - top)
        yaw, pitch = pixel_to_angles(x, y, frame.yaw, frame.pitch)
        direction = (yaw, soften_look_up(pitch))
        body.look(*direction)
        return direction
    return None


def follow_face(body, segmenter, min_score: float = 0.4) -> tuple[float, float] | None:
    """One look at where the head already faces: if a face is in view, ease the head towards it (no move of its
    own; the body language keeps going). Returns the face's direction, or None. The frame is dropped at once."""
    frame = body.capture()
    faces = [m for m in segmenter.find(frame, "face") if m.score is None or m.score >= min_score]
    if not faces:
        return None
    nearest = max(faces, key=lambda m: m.area)
    yaw, pitch = pixel_to_angles(*nearest.center, frame.yaw, frame.pitch)
    direction = (yaw, soften_look_up(pitch))
    body.face(*direction)
    return direction
