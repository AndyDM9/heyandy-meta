"""Lost and found: what a search missed, and Andy keeps looking for.

"I couldn't find your wallet" ends a conversation; "I'll keep looking, and tell you when I see it" starts a promise.
Each thing a search missed is kept here (only its word, when it was first asked for, and how many looks since), on
this computer, for up to two hours. While the room is quiet, Andy looks around for them every few minutes (spot,
below: one encoding of each view for all of them); a thing spotted is confirmed by the full search, pointed at and
said: "Good news: your wallet turned up!" (app.py _look_again). Found, given up on, or "stop looking": it's dropped.
"""
import json
import time
from pathlib import Path

from ..finder.geometry import Sighting, merge, pixel_to_angles
from ..finder.search import VIEWS
from ..private import write_private

LOOK_FOR_S = 2 * 3600  # how long a promise to keep looking lasts
LOOK_EVERY_S = 3 * 60  # a look around this often while something is lost (the watched-things glance is every 5 min)
SPOT_SCORE = 0.5  # a spotting only starts the full search, which checks it; but a weak mask isn't worth the trip


class Lost:
    def __init__(self, path: Path | str, clock=time.time):
        self.path, self.clock = Path(path), clock
        try:
            self._things: dict[str, dict] = json.loads(self.path.read_text()).get("things", {}) if self.path.exists() else {}
        except ValueError:
            self._things = {}

    def add(self, thing: str) -> bool:
        """Keep looking for it. True if it's new (a thing asked for again keeps its first time and its looks)."""
        if thing in self._things and self.clock() - self._things[thing]["since"] <= LOOK_FOR_S:
            return False
        self._things[thing] = {"since": self.clock(), "looks": 0}
        self._save()
        return True

    def drop(self, thing: str | None = None) -> list[str]:
        """Stop looking for it (or for everything); what was dropped."""
        gone = [t for t in self._things if thing is None or t == thing]
        for t in gone:
            del self._things[t]
        if gone:
            self._save()
        return gone

    def looking(self) -> list[str]:
        """What Andy is still looking for, oldest first; promises older than LOOK_FOR_S are let go."""
        old = [t for t, v in self._things.items() if self.clock() - v["since"] > LOOK_FOR_S]
        if old:
            self.drop_all(old)
        return sorted(self._things, key=lambda t: self._things[t]["since"])

    def drop_all(self, things: list[str]) -> None:
        for t in things:
            self._things.pop(t, None)
        self._save()

    def looked(self, things: list[str]) -> None:
        for t in things:
            if t in self._things:
                self._things[t]["looks"] += 1
        self._save()

    def since(self, thing: str) -> float | None:
        return self._things.get(thing, {}).get("since")

    def looks(self, thing: str) -> int:
        return self._things.get(thing, {}).get("looks", 0)

    def _save(self) -> None:
        write_private(self.path, json.dumps({"things": self._things}))


def spot(body, segmenter, labels: list[str], views=VIEWS, min_score: float = SPOT_SCORE) -> dict[str, tuple[float, float]]:
    """One look around for several things at once: where each was seen best (yaw, pitch). Every frame is dropped."""
    seen: dict[str, list[Sighting]] = {label: [] for label in labels}
    for yaw, pitch in views:
        if not body.reach.allows(yaw, pitch):
            continue
        body.look(yaw, pitch, precise=False)
        frame = body.capture()
        many = getattr(segmenter, "find_many", None)
        found = many(frame, labels) if many else {label: segmenter.find(frame, label) for label in labels}
        for label in labels:
            for m in found.get(label, []):
                score = m.score if m.score is not None else 0.5
                if score >= min_score:
                    seen[label].append(Sighting(*pixel_to_angles(*m.center, frame.yaw, frame.pitch), score))
        del frame
    out = {}
    for label, sightings in seen.items():
        best = merge(sightings)
        if best:
            out[label] = (best[0].yaw, best[0].pitch)
    return out
