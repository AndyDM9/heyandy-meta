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

from ..models.common import Mask, is_local
from ..robot.body import Frame

SYSTEM = ("Reasoning effort: low. You look at pictures from a small home robot's camera and answer in one word or "
          "one number, nothing else.")


DESCRIBE = ("Say in one or two short spoken sentences what you see{where}. Plain words, no lists. If it's a medicine "
            "or a document, say only what kind of thing it is, never what to do with it.")


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
        self.unavailable = 0  # checks skipped because Glimmer couldn't be reached
        self.calls = 0
        self.why = ""  # the last answer, for the TV's plan list

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.endpoint, api_key="local", timeout=20.0)
        return self._client

    def _ask(self, content: list) -> str | None:
        self.calls += 1
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
        return self._ask([{"type": "text", "text": DESCRIBE.format(where=f" {where}" if where else "")}, _image(image)])

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
