"""Picture checks on this computer, with Muse Glimmer's perception encoder. Pictures never leave the house.

Two questions about what SAM 3.1 found:
- real(frame, mask): a real thing, or a picture of one on a TV, a screen or in a photo? (A2)
- pick(found, description): which of several look-alikes fits the person's words, "the blue mug by the laptop"? (A1)

Glimmer is reached only at a local address; a cloud address is refused in code. If Glimmer can't be reached, the check
steps aside and the finder carries on with SAM 3.1 alone, rather than the robot going quiet.
"""
import base64
import io
import re

from openai import APIError
from PIL import Image

from ..models import glimmer_fast
from ..models.common import Mask, is_local
from ..robot.body import Frame

SYSTEM = ("Reasoning effort: low. You look at pictures from a small home robot's camera and answer in one word or "
          "one number, nothing else.")


DESCRIBE = ("Say in one or two short spoken sentences what you see{where}. Plain words, no lists. If it's a medicine "
            "or a document, say only what kind of thing it is, never what to do with it.")


POINTING = ("Look at the person's hands. Is someone pointing at something with a finger or hand? If so, what are they "
            "pointing at, and where is it in the picture? Answer exactly as: THING | SIDE. THING is a short everyday name "
            "for it that a camera could find, like 'mug', 'lamp', 'TV' or 'book'. SIDE is one of: left, middle, right, off "
            "the left edge, off the right edge. If no one is pointing, answer: NONE")


NEAR = ("Where is the {label} in the middle of this picture, by what's around it? Answer with a few words only, like "
        "'on the desk, next to the mug' or 'on the sofa arm'. No full sentence.")


class NotLocal(ValueError):
    pass


def crop(jpeg: bytes, box: tuple[int, int, int, int], context: float = 3.0, min_side: int = 256,
         max_side: int = 768) -> bytes:
    """A square around the thing, `context` times its size so its surroundings show, as a smaller JPEG."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    left, top, right, bottom = box
    side = min(max((right - left) * context, (bottom - top) * context, min_side), img.width, img.height)
    x = min(max((left + right) / 2 - side / 2, 0), img.width - side)
    y = min(max((top + bottom) / 2 - side / 2, 0), img.height - side)
    part = img.crop((round(x), round(y), round(x + side), round(y + side)))
    if part.width > max_side:
        part = part.resize((max_side, max_side))
    out = io.BytesIO()
    part.save(out, "JPEG", quality=85)
    return out.getvalue()


def shrink(jpeg: bytes, max_side: int = 1024) -> bytes:
    """A whole frame, smaller: Glimmer's encoder doesn't need 1080p to say what's on a table, and it's much faster."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def _image(jpeg: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}


class GlimmerJudge:
    def __init__(self, model: str = "muse-glimmer-30B", endpoint: str = "http://127.0.0.1:8080/v1", client=None,
                 max_tokens: int = 256):
        if not is_local(endpoint):
            raise NotLocal(f"picture checks run only on this computer, not at {endpoint}")
        self.model, self.endpoint, self._client, self.max_tokens = model, endpoint, client, max_tokens
        self.fast = client is None  # straight to the answer, past Glimmer's reasoning (models/glimmer_fast.py)
        self.unavailable = 0  # checks skipped because Glimmer couldn't be reached
        self.calls = 0
        self.why = ""  # the last answer, for the TV's plan list

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.endpoint, api_key="local", timeout=20.0)
        return self._client

    def _ask(self, content: list, max_tokens: int | None = None, think: bool = False) -> str | None:
        self.calls += 1
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
        if self.fast and not think:
            try:
                return glimmer_fast.answer(self.endpoint, messages, max_tokens or 24)
            except glimmer_fast.FastUnavailable:
                pass  # the usual way, below
        try:
            out = self.client.chat.completions.create(
                model=self.model, max_tokens=self.max_tokens,
                extra_body={"chat_template_kwargs": {"reasoning_strength": "low"}},
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}])
        except APIError:
            self.unavailable += 1
            return None
        return (out.choices[0].message.content or "").strip()

    def real(self, frame: Frame, mask: Mask) -> bool:
        """False only when Glimmer says it's a picture; unsure or unreachable counts as real (SAM already saw it twice)."""
        answer = self._ask([
            {"type": "text", "text": f"Is the {mask.label} in the middle of this picture a real, physical "
                                     f"{mask.label}, or only a picture of one (on a TV, a computer or phone screen, a "
                                     "poster or a photo)? Answer REAL or PICTURE."},
            _image(crop(frame.image, mask.box))])
        words = set(re.findall(r"[A-Z]+", (answer or "").upper()))
        picture = "PICTURE" in words and "REAL" not in words
        self.why = "a picture on a screen or in a photo" if picture else ""
        return not picture

    def describe(self, frame: Frame, where: str = "", box=None) -> str | None:
        """What's in view ("in the person's hands", "on the table"), in a sentence or two; None if Glimmer is away."""
        image = crop(frame.image, box, context=1.6, min_side=448, max_side=1024) if box else shrink(frame.image)
        return self._ask([{"type": "text", "text": DESCRIBE.format(where=f" {where}" if where else "")}, _image(image)],
                         max_tokens=120)

    def pointing(self, frame: Frame) -> tuple[str, str] | None:
        """What the person in view is pointing at, and where in the picture: ("lamp", "left"); None if no one is.
        With Glimmer's reasoning: on 8 public photos it named 4 of 6 pointed-at things and imagined none (research.md,
        25); without it, 2 of 6."""
        answer = self._ask([{"type": "text", "text": POINTING.replace("Answer exactly", "Answer in the format asked, exactly")},
                            _image(shrink(frame.image, 1024))], think=True)
        if not answer or "NONE" in answer.upper() or "|" not in answer:
            return None
        thing, side = (x.strip().strip(".").lower() for x in answer.split("|", 1))
        thing = re.sub(r"^(?:the|a|an|his|her|their|my|your)\s+", "", thing)
        return (thing, side) if thing and len(thing) <= 40 else None

    def where_near(self, frame: Frame, mask: Mask) -> str | None:
        """Where the thing is, by what's around it, in a few words ("on the desk, next to the mug")."""
        answer = self._ask([{"type": "text", "text": NEAR.format(label=mask.label)},
                            _image(crop(frame.image, mask.box, context=4.0, min_side=384, max_side=768))], max_tokens=40)
        return (answer or "").strip().strip(".").strip() or None

    def pick(self, found: list[tuple[Frame, Mask]], description: str) -> int | None:
        """The index of the one that fits the description, or None if none does (or Glimmer can't be reached)."""
        if not found:
            return None
        content: list = []
        for i, (frame, mask) in enumerate(found, 1):
            content += [{"type": "text", "text": f"Picture {i}:"}, _image(crop(frame.image, mask.box))]
        content.append({"type": "text", "text": f"Which picture shows {description}? Answer with the picture's "
                                                "number only, or 0 if none of them do."})
        answer = self._ask(content)
        n = re.search(r"\d+", answer or "")
        if not n or not 1 <= int(n.group()) <= len(found):
            return None
        return int(n.group()) - 1
