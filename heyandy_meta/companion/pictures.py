"""Pictures on request, with Muse Image: "Andy, draw me a cat asleep in a sunny garden", then "make it sunset".

The words go to Muse Image through the Model API (nothing from the home: no camera picture, no voice); the picture
comes back, is shown large on the TV and saved where the person can find it to print or share. A follow-up within a
few minutes refines the same picture (the server keeps the conversation, so only the change is sent). Measured on
2026-10-27: 11 s for a picture, 30 s to refine one, 1920x1280 WebP.
"""
import base64
import time
from dataclasses import dataclass
from pathlib import Path

from ..budget import PICTURE, Budget
from ..models.retry import with_retry

MODEL = "muse-image-1.0"
FOLDER = Path.home() / "Pictures" / "Andy"


THINGS_MAP = ("A cozy hand-drawn watercolor map of one room, seen from above, warm colors, simple and uncluttered. In "
              "the middle, a small friendly white robot with two antennas, facing the top of the picture, so its left is "
              "the left of the picture and behind it is the bottom. Around it, drawn small and clearly, each with a short, "
              "large, easy-to-read label in capital letters: {things}. No other words.")


def things_words(places: list[tuple[str, str, str]]) -> str:
    """Where things are, in words: (thing, what it's near, which way from the robot). The only part about the home."""
    def way(w: str) -> str:
        return w.replace("behind me", "behind the robot").replace("my ", "the robot's ").replace("straight ahead",
                                                                                                    "in front of the robot")
    return "; ".join(f"{thing.upper()} {near + ', ' if near else ''}{way(side)}" for thing, near, side in places)


def things_map(places: list[tuple[str, str, str]]) -> str:
    """The words for Muse Image's map of where things are."""
    return THINGS_MAP.format(things=things_words(places))


class NoPicture(RuntimeError):
    pass


@dataclass
class Drawing:
    image: bytes  # WebP
    prompt: str  # everything asked for so far, for the TV
    response_id: str  # to refine it
    made: float  # time.time()


def draw(client, prompt: str, previous: Drawing | None = None, budget: Budget | None = None,
         sleep=time.sleep) -> Drawing:
    budget = budget or Budget()
    budget.check(PICTURE)
    extra = {"previous_response_id": previous.response_id} if previous else {}
    response = with_retry(lambda: client.responses.create(model=MODEL, input=prompt, **extra), sleep=sleep)
    found = next((i.result for i in getattr(response, "output", None) or []
                  if getattr(i, "type", "") == "image_generation_call" and getattr(i, "result", None)), None)
    if not found:
        raise NoPicture("Muse Image returned no picture")
    budget.record(MODEL, PICTURE)
    asked = f"{previous.prompt}; {prompt}" if previous else prompt
    return Drawing(base64.b64decode(found), asked, response.id, time.time())


def save(drawing: Drawing, folder: Path | None = None) -> Path:
    folder = folder or FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("andy-%Y-%m-%d-%H%M%S.webp", time.localtime(drawing.made))
    path.write_bytes(drawing.image)
    return path
