"""Where chosen things were last seen: a label, a direction and a time. Never a picture.

Only things the person asked the robot to keep an eye on are remembered ("keep an eye on my keys"), and "forget my
keys" removes both the wish and the place. The file is readable only by its owner.
"""
import json
import math
import threading
import time
from pathlib import Path

from ..private import write_private

DEFAULT_PATH = Path.home() / ".local/share/heyandy-meta/places.json"
MOVED_DEG = 10.0  # further than this from the last place: it moved
HISTORY = 24  # places remembered per thing: enough for its story over a few days, and its habits
HOW = ("found", "glanced", "noticed", "scanned", "seen")  # how Andy knew: a search, a glance, put down in view, the room


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
        self._data.get("homes", {}).pop(label, None)
        self._save()

    # --- homes: where a thing lives, as the person said ("my keys live here"); Andy checks they're there ---

    def set_home(self, label: str, yaw: float, pitch: float, metres: float | None = None, near: str = "",
                 when: float | None = None) -> None:
        self._data.setdefault("homes", {})[label] = {
            "yaw": round(yaw, 1), "pitch": round(pitch, 1), "near": " ".join(near.split())[:100], "set": when or time.time(),
            **({"metres": round(metres, 2)} if metres is not None else {})}
        self._save()

    def home(self, label: str) -> dict | None:
        h = self._data.get("homes", {}).get(label)
        return dict(h) if h else None

    def homes(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self._data.get("homes", {}).items()}

    def clear_home(self, label: str) -> bool:
        gone = self._data.get("homes", {}).pop(label, None) is not None
        if gone:
            self._save()
        return gone

    def at_home(self, label: str, yaw: float, pitch: float) -> bool:
        """Whether a place is the thing's home (within MOVED_DEG)."""
        h = self.home(label)
        return bool(h) and math.hypot(h["yaw"] - yaw, h["pitch"] - pitch) <= MOVED_DEG

    def home_words(self, label: str) -> str:
        """The home in words: as said when it was set, or the words of a sighting there (written in the background)."""
        h = self.home(label)
        if not h:
            return ""
        if h["near"]:
            return h["near"]
        at = [x for x in self.history(label) if x.get("near") and math.hypot(x["yaw"] - h["yaw"], x["pitch"] - h["pitch"]) <= MOVED_DEG]
        return at[-1]["near"] if at else ""

    def saw(self, label: str, yaw: float, pitch: float, when: float | None = None, metres: float | None = None,
            how: str = "seen") -> bool:
        """Remember a sighting, only of a watched thing. Returns whether it was kept. A sighting away from the last
        place starts a new entry in its history (it moved); one at the same place only updates the time. ``how`` is how
        Andy knew (HOW), for the thing's story."""
        if label not in self._data["watching"]:
            return False
        when = when or time.time()
        spot = {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "at": when, "since": when, "near": "",
                "how": how if how in HOW else "seen"}
        if metres is not None:  # how far, from MapAnything: with the direction, a place on a real map
            spot["metres"] = round(metres, 2)
        history = self._data.setdefault("history", {}).setdefault(label, [])
        last = history[-1] if history else None
        if last and math.hypot(last["yaw"] - yaw, last["pitch"] - pitch) <= MOVED_DEG and "gone" not in last:
            last["at"] = when  # still there
            if metres is not None:
                last["metres"] = round(metres, 2)
            spot = last
        else:
            history.append(spot)  # first seen, or it moved
            del history[:-HISTORY]
        self._data["seen"][label] = {"yaw": spot["yaw"], "pitch": spot["pitch"], "at": when,
                                     **({"metres": spot["metres"]} if "metres" in spot else {})}
        self._save()
        return True

    def near(self, label: str, words: str) -> None:
        """What the latest place looks like, in words ("on the desk, next to the mug"): no picture is kept."""
        history = self._data.get("history", {}).get(label)
        if history:
            history[-1]["near"] = " ".join(words.split())[:100]
            self._save()

    def picked_up(self, label: str, when: float | None = None) -> None:
        """Seen being picked up from its last place (V-JEPA 2, memory/notice.py): that place is over."""
        history = self._data.get("history", {}).get(label)
        if history and "gone" not in history[-1]:
            history[-1]["gone"] = when or time.time()
            self._save()

    def usual(self, label: str) -> dict | None:
        """Where it usually ends up: the place it has been seen at most often (within MOVED_DEG), if twice or more.
        {"yaw", "pitch", "near", "metres", "count", "of"}: count of the "of" places in its history."""
        history = self.history(label)
        groups: list[dict] = []
        for h in history:
            g = next((g for g in groups if math.hypot(g["yaw"] - h["yaw"], g["pitch"] - h["pitch"]) <= MOVED_DEG), None)
            if g is None:
                groups.append({"yaw": h["yaw"], "pitch": h["pitch"], "near": h.get("near", ""), "metres": h.get("metres"),
                               "count": 1, "last": h["at"]})
            else:
                g["count"], g["last"] = g["count"] + 1, max(g["last"], h["at"])
                g["near"], g["metres"] = h.get("near") or g["near"], h.get("metres", g["metres"])
        if not groups:
            return None
        best = max(groups, key=lambda g: (g["count"], g["last"]))
        return {k: best[k] for k in ("yaw", "pitch", "near", "metres", "count")} | {"of": len(history)} \
            if best["count"] >= 2 else None

    def history(self, label: str) -> list[dict]:
        """Where it has been, oldest first: each place with when it was first and last seen there, and its words."""
        return [dict(h) for h in self._data.get("history", {}).get(label, [])]

    def metres(self, label: str) -> float | None:
        """How far away it was when last seen (MapAnything), if that was measured."""
        return (self._data["seen"].get(label) or {}).get("metres")

    def seen_at(self, label: str) -> float | None:
        s = self._data["seen"].get(label)
        return s["at"] if s else None

    def last_seen(self, label: str, now: float | None = None) -> tuple[float, float] | None:
        """Where it was last seen, unless that's old or it was seen picked up from there since."""
        s = self._data["seen"].get(label)
        if s is None or (now or time.time()) - s["at"] > self.max_age_s:
            return None
        history = self._data.get("history", {}).get(label) or [{}]
        if history[-1].get("gone", 0) >= s["at"]:
            return None
        return s["yaw"], s["pitch"]

    def _save(self) -> None:
        with self._lock:  # a place's words are written from a background thread on the robot
            self._write()

    def _write(self) -> None:
        write_private(self.path, json.dumps(self._data))
