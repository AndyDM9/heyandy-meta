"""Things Andy knows by sight: "this is my mug". The person's own mug, told from anyone else's.

What a thing looks like is kept as numbers, never a picture: DINOv2 (Meta's open image model, on this computer) and a
colour fingerprint turn the thing's own pixels, inside SAM 3.1's mask, into a vector. A few views are kept, from when
the person held it up and turned it. When Andy finds a mug later, it's compared with them; one that isn't alike enough isn't the person's.

Stored in a small JSON file on this computer, readable only by its owner. "Forget my mug" deletes it.
"""
import json
import math
import threading
import time
from pathlib import Path

from ..private import write_private

ALIKE = 0.75  # the same thing seen from other views scored 0.79 to 0.98 on the robot; a red twin of a blue mug 0.55
#               (research.md, 19)
VIEWS = 8  # views kept for each thing


def likeness(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0  # a view kept by an older version of the model: not comparable
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class Mine:
    def __init__(self, path: Path | str, alike: float = ALIKE):
        self.path, self.alike = Path(path), alike
        self._lock = threading.Lock()
        self._things: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._things = json.loads(self.path.read_text())
            except (OSError, ValueError):
                self._things = {}

    def key(self, label: str) -> str | None:
        """The known thing a label means: "mug" finds "coffee mug", and the other way round."""
        label = label.lower().strip()
        if label in self._things or not label:
            return label or None
        if " " not in label:  # "mug" means the one mug Andy knows, "coffee mug"
            return next((k for k in self._things if k.split()[-1] == label), None)
        last = label.split()[-1]  # "coffee mug" means "mug" if that's what was learned; "house keys" isn't "car keys"
        return last if last in self._things else None

    def knows(self, label: str) -> bool:
        return self.key(label) is not None

    def known(self) -> list[str]:
        return sorted(self._things)

    def learn(self, label: str, vectors: list[list[float]], now: float | None = None) -> None:
        with self._lock:
            key = self.key(label) or label.lower().strip()
            views = (self._things.get(key, {}).get("views", []) + [list(v) for v in vectors])[-VIEWS:]
            self._things[key] = {"views": views, "learned": now if now is not None else time.time()}
            self._save()

    def forget(self, label: str) -> bool:
        with self._lock:
            key = self.key(label)
            if key is None:
                return False
            del self._things[key]
            self._save()
            return True

    def how_alike(self, label: str, vector: list[float]) -> float | None:
        """The best likeness to any kept view; None if the thing isn't known."""
        key = self.key(label)
        if key is None:
            return None
        return max(likeness(vector, v) for v in self._things[key]["views"])

    def _save(self) -> None:
        write_private(self.path, json.dumps(self._things))
