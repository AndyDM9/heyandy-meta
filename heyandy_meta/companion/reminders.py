"""Reminders the person sets, delivered in person: at the time, Andy turns to find them, looks at them, and says it.

Andy repeats the person's own words and adds nothing; it never advises (no doses, no instructions). If nobody is in
view it tries again a few minutes later, a few times, then lets the reminder go and says so next time it sees them.
The file holds only the words, the time and whether it was said, readable only by its owner.
"""
import datetime as dt
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from ..private import write_private

DEFAULT_PATH = Path.home() / ".local/share/heyandy-meta/reminders.json"
RETRY_S, TRIES = 5 * 60, 3


@dataclass
class Reminder:
    id: str
    text: str  # the person's own words
    at: float  # when it's due, epoch seconds
    daily: bool = False
    tries: int = 0
    next_try: float = 0.0
    state: str = "waiting"  # waiting | said | missed | cancelled


def spoken_time(t: float) -> str:
    d = dt.datetime.fromtimestamp(t)
    hour = d.hour % 12 or 12
    if d.minute == 0:
        return f"{hour} o'clock"
    return f"{hour}:{d.minute:02d}"


class Reminders:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        raw = json.loads(self.path.read_text()) if self.path.exists() else []
        self.items = [Reminder(**r) for r in raw]

    def add(self, text: str, at: float, daily: bool = False, now: float | None = None) -> Reminder:
        text = " ".join(text.split())
        if not text or len(text) > 140:
            raise ValueError("a reminder needs a short text, up to 140 characters")
        if at <= (now or time.time()):
            raise ValueError("a reminder must be in the future")
        r = Reminder(uuid.uuid4().hex[:8], text, at, daily, next_try=at)
        self.items.append(r)
        self._save()
        return r

    def cancel(self, rid: str) -> bool:
        for r in self.items:
            if r.id == rid and r.state == "waiting":
                r.state = "cancelled"
                self._save()
                return True
        return False

    def upcoming(self) -> list[Reminder]:
        return sorted((r for r in self.items if r.state == "waiting"), key=lambda r: r.at)

    def due(self, now: float | None = None) -> list[Reminder]:
        now = now or time.time()
        return [r for r in self.upcoming() if r.next_try <= now]

    def missed_unmentioned(self) -> list[Reminder]:
        return [r for r in self.items if r.state == "missed"]

    def deliver(self, r: Reminder, find_person, say, now: float | None = None) -> str:
        """One attempt: find the person, then say it. Returns "said", "retry" or "missed"."""
        now = now or time.time()
        if find_person() is None:
            r.tries += 1
            if r.tries >= TRIES:
                r.state = "missed"
            else:
                r.next_try = now + RETRY_S
            self._save()
            return r.state if r.state == "missed" else "retry"
        say(f"It's {spoken_time(now)}. You asked me to remind you: {r.text}")
        if r.daily:
            r.at += 24 * 3600
            r.next_try, r.tries = r.at, 0
        else:
            r.state = "said"
        self._save()
        return "said"

    def mention_missed(self, say) -> int:
        """When the person is next seen: tell them what was missed, once."""
        missed = self.missed_unmentioned()
        for r in missed:
            say(f"Earlier, at {spoken_time(r.at)}, I couldn't find you to remind you: {r.text}")
            r.state = "said"
        if missed:
            self._save()
        return len(missed)

    def _save(self) -> None:
        write_private(self.path, json.dumps([asdict(r) for r in self.items]))
