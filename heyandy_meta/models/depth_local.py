"""How far away is it: Meta's MapAnything, through local/depth_server.py on this computer. Pictures go only here."""
import base64
import json
import time
import urllib.error
import urllib.request

from .common import Mask, is_local
from .sam_local import LocalUnavailable, NotLocal


class LocalDepth:
    def __init__(self, endpoint: str = "http://127.0.0.1:8096", timeout: float = 5.0):
        if not is_local(endpoint):
            raise NotLocal(f"MapAnything must be on this computer or the home network, not {endpoint}")
        self.endpoint, self.timeout = endpoint.rstrip("/"), timeout
        self.last_latency_s = 0.0

    def distances(self, frame, masks: list[Mask], cam) -> list[float | None]:
        """Metres from the camera to the middle of each masked thing (None: no sure depth there). ``cam`` is the
        camera at the frame's own size (its focal length and centre, in pixels)."""
        body = {"image": base64.b64encode(frame.image).decode(), "fx": cam.fx, "cx": cam.cx, "cy": cam.cy,
                "boxes": [list(m.box) for m in masks]}
        req = urllib.request.Request(self.endpoint + "/distance", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LocalUnavailable(f"MapAnything at {self.endpoint}: {e}") from e
        self.last_latency_s = time.monotonic() - start
        return [t["metres"] if t else None for t in out["things"]]


def how_far(metres: float) -> str:
    """In words, as people in the US say it, and only roughly: the depth is good to about a tenth."""
    feet = round(metres * 3.281)
    return "about a foot away" if feet <= 1 else f"about {feet} feet away"
