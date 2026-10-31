"""What the person told Andy: "I'm putting my passport in the top drawer of the desk."

Andy's camera sees one room; the things people dread losing (a passport, the spare key, the warranty) are in drawers,
bags and other rooms. People know where they put them when they put them, and forget later. So Andy keeps what it's
told, as the person's own words with when they said it, on this computer, and answers from them at once ("You told me
on Tuesday at 3:12: in the top drawer of the desk"); asked again, it looks around the room. Seen since by the camera,
the camera's place wins. "Forget my passport" removes it.
"""
import json
import re
import time
from pathlib import Path

from ..private import write_private

KEEP = 5  # the last few places told for each thing
TOLD_FOR_S = 365 * 24 * 3600  # a passport stays in its drawer for months


class Told:
    def __init__(self, path: Path | str, clock=time.time):
        self.path, self.clock = Path(path), clock
        try:
            self._things: dict[str, list[dict]] = json.loads(self.path.read_text()) if self.path.exists() else {}
        except ValueError:
            self._things = {}

    def tell(self, thing: str, words: str) -> None:
        notes = self._things.setdefault(thing, [])
        notes.append({"words": " ".join(words.split())[:120], "at": self.clock()})
        del notes[:-KEEP]
        self._save()

    def latest(self, thing: str) -> dict | None:
        """The last place told for it, unless that was over a year ago."""
        notes = self._things.get(thing) or []
        if not notes or self.clock() - notes[-1]["at"] > TOLD_FOR_S:
            return None
        return dict(notes[-1])

    def all(self) -> dict[str, dict]:
        return {t: n for t in self._things if (n := self.latest(t))}

    def forget(self, thing: str) -> bool:
        gone = self._things.pop(thing, None) is not None
        if gone:
            self._save()
        return gone

    def _save(self) -> None:
        write_private(self.path, json.dumps(self._things))


def yours(words: str) -> str:
    """The person's words, said back: "in my bag" -> "in your bag"."""
    swaps = {"my": "your", "our": "your", "me": "you", "mine": "yours", "i": "you", "myself": "yourself"}
    return re.sub(r"\b(my|our|me|mine|i|myself)\b", lambda m: swaps[m.group(1).lower()], words, flags=re.I)
