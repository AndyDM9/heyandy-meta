"""While idle, look around once and note where watched things are. Runs on local SAM 3.1: at API prices a glance
every few minutes would cost about $20 a day."""
from ..finder.geometry import Sighting, merge, pixel_to_angles
from ..finder.search import VIEWS, Segmenter
from ..robot.body import Body
from .places import Places


def glance(body: Body, segmenter: Segmenter, places: Places, views=VIEWS, min_score: float = 0.5) -> dict[str, tuple]:
    """One look around. Returns what was noted, label -> (yaw, pitch). The frames are dropped as soon as they're read."""
    labels = places.watching()
    if not labels:
        return {}
    seen: dict[str, list[Sighting]] = {label: [] for label in labels}
    for yaw, pitch in views:
        if not body.reach.allows(yaw, pitch):
            continue
        body.look(yaw, pitch, precise=False)
        frame = body.capture()
        for label in labels:
            for m in segmenter.find(frame, label):
                if m.score is not None and m.score < min_score:
                    continue
                y, p = pixel_to_angles(*m.center, frame.yaw, frame.pitch)
                seen[label].append(Sighting(y, p, m.score if m.score is not None else 0.5))
        del frame
    noted = {}
    for label, sightings in seen.items():
        places_ = merge(sightings)
        if places_:
            best = places_[0]
            places.saw(label, best.yaw, best.pitch)
            noted[label] = (best.yaw, best.pitch)
    return noted
