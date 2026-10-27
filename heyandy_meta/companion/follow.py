"""Follow a thing with the eyes as someone moves it: "Andy, follow the mug."

SAM 3.1 finds the thing in each frame (about twice a second, on this computer), the nearest mask to where it was last
is taken as the same thing, and the head eases after it; past the head's reach the base turns. It ends when told to
stop, after a while, or when the thing has been out of sight for a few frames.
"""
import math
import time

from ..finder.geometry import pixel_to_angles


def follow(body, segmenter, label: str, start: tuple[float, float], on_frame, stop, seconds: float = 30.0,
           lose_after: int = 6, min_score: float = 0.3, clock=time.monotonic) -> str:
    """Returns why it ended: "stopped", "time" or "lost"."""
    last, missed, deadline = start, 0, clock() + seconds
    head_reach = getattr(body, "head_yaw", 30.0) - 5.0
    while not stop():
        if clock() >= deadline:
            return "time"
        frame = body.capture()
        masks = [m for m in segmenter.find(frame, label) if m.score is None or m.score >= min_score]
        if not masks:
            missed += 1
            if missed >= lose_after:
                return "lost"
            continue
        missed = 0
        seen = [(m, pixel_to_angles(*m.center, frame.yaw, frame.pitch)) for m in masks]
        mask, (yaw, pitch) = min(seen, key=lambda s: math.hypot(s[1][0] - last[0], s[1][1] - last[1]))
        on_frame(frame, mask, yaw, pitch)
        face = getattr(body, "face", None)
        base = getattr(body, "_sent", (0.0, 0.0, 0.0))[2]
        if face and abs(yaw - base) <= head_reach:
            face(yaw, pitch)  # the body-language loop eases the head there: smooth, no stop-start
        else:
            body.look(yaw, pitch, precise=False)  # further round: turn the base too
        last = (yaw, pitch)
    return "stopped"
