"""How far away is it: Meta's MapAnything, through local/depth_server.py on this computer. Pictures go only here."""
import base64
import json
import math
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

    def scan(self, looks: list[tuple], timeout: float = 60.0) -> dict:
        """The room's shape from several looks: [(frame, cam, masks)], each frame taken where the head faced. Returns
        {"points": float16 bytes (n x 3, metres: x right, y down, z ahead), "n", "things": [{"label", "point",
        "metres", "score"}], "seconds"}. Shape only; the frames go no further than MapAnything on this computer."""
        views = [{"image": base64.b64encode(f.image).decode(), "fx": cam.fx, "cx": cam.cx, "cy": cam.cy,
                  "pose": pose(f.yaw, f.pitch),
                  "boxes": [{"label": m.label, "box": list(m.box), "score": m.score} for m in masks]}
                 for f, cam, masks in looks]
        req = urllib.request.Request(self.endpoint + "/scan", json.dumps({"views": views}).encode(),
                                     {"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LocalUnavailable(f"MapAnything at {self.endpoint}: {e}") from e
        self.last_latency_s = time.monotonic() - start
        out["points"] = base64.b64decode(out["points"])
        return out


def pose(yaw: float, pitch: float) -> list[list[float]]:
    """The camera's pose in the room for a head direction (degrees; yaw left positive, pitch down positive), in the
    camera's own axes at yaw 0, pitch 0: x right, y down, z ahead. The camera turns about its own centre."""
    y, p = math.radians(-yaw), math.radians(-pitch)
    ry = [[math.cos(y), 0.0, math.sin(y)], [0.0, 1.0, 0.0], [-math.sin(y), 0.0, math.cos(y)]]
    rx = [[1.0, 0.0, 0.0], [0.0, math.cos(p), -math.sin(p)], [0.0, math.sin(p), math.cos(p)]]
    r = [[sum(ry[i][k] * rx[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return [r[0] + [0.0], r[1] + [0.0], r[2] + [0.0], [0.0, 0.0, 0.0, 1.0]]


def how_far(metres: float, metric: bool = False) -> str:
    """In words, and only roughly (the depth is good to about a tenth): feet, as people in the US say it, or metres
    (Spanish: then translated, "a unos 60 centímetros")."""
    if metric:
        if metres < 0.95:
            return f"about {max(10, round(metres * 10) * 10)} centimetres away"
        half = round(metres * 2) / 2
        return "roughly one metre away" if half == 1 else f"about {half:g} metres away"  # "a metre": "unos metros"
    feet = round(metres * 3.281)
    return "about a foot away" if feet <= 1 else f"about {feet} feet away"
