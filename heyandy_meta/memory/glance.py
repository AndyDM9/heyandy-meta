"""While idle, look around once and note where watched things are. Runs on local SAM 3.1: at API prices a glance
every few minutes would cost about $20 a day."""
from ..finder.geometry import Sighting, merge, pixel_to_angles
from ..finder.search import VIEWS, Segmenter
from ..robot.body import Body
from .places import Places


def glance(body: Body, segmenter: Segmenter, places: Places, views=VIEWS, min_score: float = 0.5,
           on_seen=None) -> dict[str, tuple]:
    """One look around. Returns what was noted, label -> (yaw, pitch). on_seen(label, frame, mask) is shown the best
    view of each thing noted (to describe the place in words); then every frame is dropped."""
    labels = places.watching()
    if not labels:
        return {}
    seen: dict[str, list[Sighting]] = {label: [] for label in labels}
    best_view: dict[str, tuple] = {}  # label -> (score, frame, mask), in memory for this glance only
    for yaw, pitch in views:
        if not body.reach.allows(yaw, pitch):
            continue
        body.look(yaw, pitch, precise=False)
        frame = body.capture()
        many = getattr(segmenter, "find_many", None)
        found = many(frame, labels) if many else {label: segmenter.find(frame, label) for label in labels}
        for label in labels:
            for m in found[label]:
                if m.score is not None and m.score < min_score:
                    continue
                y, p = pixel_to_angles(*m.center, frame.yaw, frame.pitch)
                score = m.score if m.score is not None else 0.5
                seen[label].append(Sighting(y, p, score))
                if on_seen and score > best_view.get(label, (-1,))[0]:
                    best_view[label] = (score, frame, m)
        del frame
    noted = {}
    for label, sightings in seen.items():
        places_ = merge(sightings)
        if places_:
            best = places_[0]
            places.saw(label, best.yaw, best.pitch, how="glanced")
            noted[label] = (best.yaw, best.pitch)
            if on_seen and label in best_view:
                on_seen(label, best_view[label][1], best_view[label][2])
    best_view.clear()
    return noted
