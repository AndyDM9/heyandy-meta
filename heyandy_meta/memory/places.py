"""Where chosen things were last seen: a label, a direction and a time. Never a picture.

Only things the person asked the robot to keep an eye on are remembered ("keep an eye on my keys"), and "forget my
keys" removes both the wish and the place. The file is readable only by its owner.
"""
import json
import os
import time
from pathlib import Path

DEFAULT_PATH = Path.home() / ".local/share/heyandy-meta/places.json"


class Places:
    def __init__(self, path: Path | str = DEFAULT_PATH, max_age_s: float = 3 * 24 * 3600):
        self.path, self.max_age_s = Path(path), max_age_s
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
        self._save()

    def saw(self, label: str, yaw: float, pitch: float, when: float | None = None) -> bool:
        """Remember a sighting, only of a watched thing. Returns whether it was kept."""
        if label not in self._data["watching"]:
            return False
        self._data["seen"][label] = {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "at": when or time.time()}
        self._save()
        return True

    def last_seen(self, label: str, now: float | None = None) -> tuple[float, float] | None:
        s = self._data["seen"].get(label)
        if s is None or (now or time.time()) - s["at"] > self.max_age_s:
            return None
        return s["yaw"], s["pitch"]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
