"""SAM 3.1 through the Meta Model API: a noun phrase and a frame in, masks out."""
import base64
import os
import time

from meta_sam_parser import (
    CompletedOutcome,
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    decode_mask_to_svg_path,
    image_segmentation_format,
)

from ..budget import SAM_PER_IMAGE, Budget
from .common import Mask, sam_asks
from .retry import with_retry

BASE_URL = "https://api.meta.ai/v1"


def parse(output_text: str, label: str) -> list[Mask]:
    """Turn SAM 3.1's output text into masks with their centres. An empty text means nothing was found."""
    parser = image_segmentation_format().create_parser()
    parser.push(output_text)
    result = parser.finish(CompletedOutcome()).result
    box_scores = {r.object_id: r.confidence for r in result.records if isinstance(r, SegmentationBoxRecord)}
    masks = []
    for record in result.records:
        if not isinstance(record, SegmentationMaskRecord):
            continue
        center, area = _center(record)
        if area == 0:
            continue
        b = record.bounds
        score = record.confidence if record.confidence is not None else box_scores.get(record.object_id)
        scale = ((b.right - b.left) / record.mask.width, (b.bottom - b.top) / record.mask.height)
        masks.append(Mask(label=label, box=(int(b.left), int(b.top), int(b.right), int(b.bottom)),
                          score=score, center=center, area=area,
                          outline=decode_mask_to_svg_path(record.mask), outline_scale=scale))
    return sorted(masks, key=lambda m: -(m.score if m.score is not None else 0.0))


def _center(record: SegmentationMaskRecord) -> tuple[tuple[float, float], int]:
    """Centre of mass of a box-local raster, mapped to frame pixels."""
    w, h = record.mask.width, record.mask.height
    raster = decode_mask_to_raster(record.mask)
    b = record.bounds
    sx, sy = (b.right - b.left) / w, (b.bottom - b.top) / h
    n = xs = ys = 0
    for i, bit in enumerate(raster):
        if bit:
            n += 1
            xs += i % w
            ys += i // w
    if n == 0:
        return (0.0, 0.0), 0
    return (b.left + (xs / n + 0.5) * sx, b.top + (ys / n + 0.5) * sy), n


def request(image: bytes, query: str, mime: str = "image/jpeg") -> dict:
    """The Responses API arguments for one frame. A data URL is assumed to be accepted; checked on the first paid call (P5)."""
    data_url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    return {
        "model": "sam-3.1",
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": query},
            {"type": "input_image", "image_url": data_url},
        ]}],
        "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"},
    }


class Sam31Segmenter:
    def __init__(self, client=None, api_key_env: str = "MODEL_API_KEY", base_url: str = BASE_URL,
                 budget: Budget | None = None, sleep=time.sleep):
        self._client, self.budget, self._sleep = client, budget or Budget(), sleep
        self._api_key_env, self._base_url = api_key_env, base_url
        self.last_latency_s = 0.0

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            key = os.environ.get(self._api_key_env)
            if not key:
                raise RuntimeError(f"{self._api_key_env} is not set")
            self._client = OpenAI(base_url=self._base_url, api_key=key)
        return self._client

    def find(self, frame, query: str) -> list[Mask]:
        """``frame`` is a robot Frame or raw JPEG bytes."""
        image = getattr(frame, "image", frame)
        self.budget.check(SAM_PER_IMAGE)
        start = time.monotonic()
        def call():
            with self.client.responses.stream(**request(image, sam_asks(query))) as stream:
                return stream.get_final_response().output_text or ""

        text = with_retry(call, sleep=self._sleep)
        self.last_latency_s = time.monotonic() - start
        self.budget.record("sam-3.1", SAM_PER_IMAGE)
        return parse(text, query)
