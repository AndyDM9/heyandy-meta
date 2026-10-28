"""SAM 3.1 from the open weights, through local/sam_server.py on this computer. Pictures from a home go only here."""
import base64
import json
import time
import urllib.error
import urllib.request

from dataclasses import dataclass

from .common import Mask, is_local


@dataclass
class Track:
    """One thing followed through a clip: where it was in each frame it was seen, and its mask in the last frame."""

    id: int
    path: list[tuple[int, float, float]]  # (frame, x, y) in the clip's pixels
    end: Mask | None  # None: not seen in the last frame (lost)


class NotLocal(ValueError):
    pass


class LocalUnavailable(RuntimeError):
    pass


class LocalSam31:
    def __init__(self, endpoint: str = "http://127.0.0.1:8090", timeout: float = 10.0, min_score: float = 0.3):
        if not is_local(endpoint):
            raise NotLocal(f"local SAM 3.1 must be on this computer or the home network, not {endpoint}")
        self.endpoint, self.timeout, self.min_score = endpoint.rstrip("/"), timeout, min_score
        self.last_latency_s = 0.0

    def _post(self, path: str, frame_or_bytes, **fields) -> dict:
        image = getattr(frame_or_bytes, "image", frame_or_bytes)
        return self._send(path, {"image": base64.b64encode(image).decode(), "min_score": self.min_score, **fields})

    def _send(self, path: str, fields: dict, timeout: float | None = None) -> dict:
        req = urllib.request.Request(self.endpoint + path, json.dumps(fields).encode(), {"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                out = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as e:  # OSError: timeouts, a dropped connection
            raise LocalUnavailable(f"local SAM 3.1 at {self.endpoint}: {e}") from e
        self.last_latency_s = time.monotonic() - start
        return out

    def find(self, frame_or_bytes, query: str) -> list[Mask]:
        return [_mask(query, m) for m in self._post("/segment", frame_or_bytes, query=query)["masks"]]

    def find_many(self, frame_or_bytes, queries: list[str]) -> dict[str, list[Mask]]:
        """Several things in one frame, encoded once (SAM 3.1 keeps the frame's features for every prompt)."""
        out = self._post("/segment_many", frame_or_bytes, queries=list(queries))["masks"]
        return {q: [_mask(q, m) for m in out.get(q, [])] for q in queries}


    def embed(self, frame_or_bytes, masks: list[Mask]) -> list[list[float]]:
        """What each masked thing looks like, as numbers (DINOv2 on this computer), from its own pixels only."""
        image = getattr(frame_or_bytes, "image", frame_or_bytes)
        return self._send("/embed", {"image": base64.b64encode(image).decode(), "masks": [
            {"box": list(m.box), "outline": m.outline, "outline_scale": list(m.outline_scale)} for m in masks]})["vectors"]

    def guard(self, texts: list[str]) -> list[float]:
        """Llama Prompt Guard 2 on this computer: how likely each text is trying to instruct Andy (0 to 1)."""
        return self._send("/guard", {"texts": list(texts)})["scores"]

    def track(self, frames: list, query: str) -> list[Track]:
        """Every ``query`` in the first frame, followed through the clip by SAM 3.1 Object Multiplex (about 5 frames a
        second on this computer's GPU, so a few seconds of shuffling takes a few more to replay)."""
        images = [base64.b64encode(getattr(f, "image", f)).decode() for f in frames]
        out = self._send("/track", {"frames": images, "query": query}, timeout=30.0 + len(images) / 2)
        return [Track(o["id"], [tuple(p) for p in o["path"]], _mask(query, o["end"]) if o["end"] else None)
                for o in out["objects"]]


def _mask(label: str, m: dict) -> Mask:
    return Mask(label=label, box=tuple(m["box"]), score=m["score"], center=tuple(m["center"]), area=m["area"],
                outline=m["outline"], outline_scale=tuple(m["outline_scale"]))
