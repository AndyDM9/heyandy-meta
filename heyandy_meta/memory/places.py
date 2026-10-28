"""Where chosen things were last seen: a label, a direction and a time. Never a picture.

Only things the person asked the robot to keep an eye on are remembered ("keep an eye on my keys"), and "forget my
keys" removes both the wish and the place. The file is readable only by its owner.
"""
import json
import math
import os
import threading
import time
from pathlib import Path

DEFAULT_PATH = Path.home() / ".local/share/heyandy-meta/places.json"
MOVED_DEG = 10.0  # further than this from the last place: it moved
HISTORY = 8  # places remembered per thing


class Places:
    def __init__(self, path: Path | str = DEFAULT_PATH, max_age_s: float = 3 * 24 * 3600):
        self.path, self.max_age_s = Path(path), max_age_s
        self._lock = threading.RLock()
        self._data = json.loads(self.path.read_text()) if self.path.exists() else {"watching": [], "seen": {}}

    def watching(self) -> list[str]:
        return list(self._data["watching"])

    def watch(self, label: str) -> None:
        if label not in self._data["watching"]:
            self._data["watching"].append(label)
            self._save()

    def forget(self, label: str) -> None:
        if label in self._data["watching"]:
            self._data["watching"].remove(label)
        self._data["seen"].pop(label, None)
        self._data.get("history", {}).pop(label, None)
        self._save()

    def saw(self, label: str, yaw: float, pitch: float, when: float | None = None) -> bool:
        """Remember a sighting, only of a watched thing. Returns whether it was kept. A sighting away from the last
        place starts a new entry in its history (it moved); one at the same place only updates the time."""
        if label not in self._data["watching"]:
            return False
        when = when or time.time()
        spot = {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "at": when, "since": when, "near": ""}
        history = self._data.setdefault("history", {}).setdefault(label, [])
        last = history[-1] if history else None
        if last and math.hypot(last["yaw"] - yaw, last["pitch"] - pitch) <= MOVED_DEG:
            last["at"] = when  # still there
            spot = last
        else:
            history.append(spot)  # first seen, or it moved
            del history[:-HISTORY]
        self._data["seen"][label] = {"yaw": spot["yaw"], "pitch": spot["pitch"], "at": when}
        self._save()
        return True

    def near(self, label: str, words: str) -> None:
        """What the latest place looks like, in words ("on the desk, next to the mug"): no picture is kept."""
        history = self._data.get("history", {}).get(label)
        if history:
            history[-1]["near"] = " ".join(words.split())[:100]
            self._save()

    def history(self, label: str) -> list[dict]:
        """Where it has been, oldest first: each place with when it was first and last seen there, and its words."""
        return [dict(h) for h in self._data.get("history", {}).get(label, [])]

    def seen_at(self, label: str) -> float | None:
        s = self._data["seen"].get(label)
        return s["at"] if s else None

    def last_seen(self, label: str, now: float | None = None) -> tuple[float, float] | None:
        s = self._data["seen"].get(label)
        if s is None or (now or time.time()) - s["at"] > self.max_age_s:
            return None
        return s["yaw"], s["pitch"]

    def _save(self) -> None:
        with self._lock:  # a place's words are written from a background thread on the robot
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
