"""SAM 3.1 from the open weights, through local/sam_server.py on this computer. Pictures from a home go only here."""
import base64
import json
import time
import urllib.error
import urllib.request

from .common import Mask, is_local


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

    def find(self, frame_or_bytes, query: str) -> list[Mask]:
        image = getattr(frame_or_bytes, "image", frame_or_bytes)
        body = json.dumps({"image": base64.b64encode(image).decode(), "query": query, "min_score": self.min_score})
        req = urllib.request.Request(self.endpoint + "/segment", body.encode(), {"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.load(r)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise LocalUnavailable(f"local SAM 3.1 at {self.endpoint}: {e}") from e
        self.last_latency_s = time.monotonic() - start
        return [Mask(label=query, box=tuple(m["box"]), score=m["score"], center=tuple(m["center"]), area=m["area"],
                     outline=m["outline"], outline_scale=tuple(m["outline_scale"])) for m in out["masks"]]
