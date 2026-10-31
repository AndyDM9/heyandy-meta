"""How far away is it? Meta's MapAnything (open weights, Apache-2.0) on this computer: a frame and masks in, metres out.

MapAnything (Meta Reality Labs and Carnegie Mellon, `facebook/map-anything-apache`) gives metric depth and a 3D point
for every pixel of one camera frame, told the camera's focal length and centre. Andy asks it for the things SAM 3.1
found, so a find says how far away the thing is, and a remembered place has a distance, not only a direction.

Runs in its own environment (~/opt/mapanything: PyTorch and Meta's `mapanything` package; scripts/setup-depth.sh)
on GPU 1 beside SAM 3.1, in about 3 GB: the encoder and the view-fusing transformer in bf16, the rest in fp32. It
listens on 127.0.0.1 only. Frames are held in memory for one request and never written or logged.

    CUDA_VISIBLE_DEVICES=1 ~/opt/mapanything/.venv/bin/python local/depth_server.py

POST /distance {"image": <base64 JPEG>, "fx": 1054, "cx": 953, "cy": 542,
                "boxes": [[l, t, r, b], ...]}            (the frame's own pixels)
  -> {"things": [{"metres": 1.42, "point": [x, y, z]} or null, ...], "seconds": 0.16}
     metres: straight-line distance from the camera to the middle of the thing (the median over the inner half of
     its box, where the pixels are the thing's own); point: camera coordinates in metres, x right, y down, z forward.
     null: no reliable depth there (MapAnything masks its unsure edges).

POST /scan {"views": [{"image": <base64 JPEG>, "fx", "cx", "cy", "pose": 4x4 camera-to-room,
                       "boxes": [{"label": "keys", "box": [l, t, r, b], "score": 0.9}, ...]}, ...]}   (2 to 6 views)
  -> {"points": <base64 float16, n x 3>, "n": 21000, "things": [{"label", "point": [x, y, z], "metres", "score"}],
      "seconds": 1.9}
     The views together, the head's own angles given as each camera's pose, so they join in one room: x right, y
     down, z ahead of the robot, in metres, the camera at the middle. Shape only: no colour leaves this server, the
     points are thinned to one per 3 cm cube, and nothing is kept after the answer.

Measured before building (public NYU Depth v2 test frames, ground truth from a Kinect): 13% median error, and it
reads closer than true by about that much, so Andy says "about". A tape measure in the robot's own room calibrates
it: HEYANDY_DEPTH_SCALE (default 1.0) multiplies every distance.
"""
import argparse
import base64
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

MODEL = "facebook/map-anything-apache"
MAX_BODY = 12 * 1024 * 1024
SCALE = float(os.environ.get("HEYANDY_DEPTH_SCALE", "1.0"))


def load():
    from mapanything.models import MapAnything

    model = MapAnything.from_pretrained(MODEL).eval()
    model.encoder.to(torch.bfloat16)  # the two big parts in bf16: about 3 GB instead of 5, the same accuracy
    model.info_sharing.to(torch.bfloat16)

    def fp32(module, inputs, out):  # hand the encoder's features back to the fp32 parts after it
        if hasattr(out, "features"):
            out.features = out.features.float()
        return out.float() if torch.is_tensor(out) else out

    model.encoder.register_forward_hook(fp32)
    return model.cuda()


def inner(box, w: int, h: int, sx: float, sy: float):
    """The middle half of a box, in the depth map's pixels: the thing's own pixels, not the table behind its edge."""
    l, t, r, b = box
    cx, cy, hw, hh = (l + r) / 2, (t + b) / 2, max(1.0, (r - l) / 4), max(1.0, (b - t) / 4)
    x0, x1 = int(max(0, (cx - hw) * sx)), int(min(w, max((cx - hw) * sx + 1, (cx + hw) * sx)))
    y0, y1 = int(max(0, (cy - hh) * sy)), int(min(h, max((cy - hh) * sy + 1, (cy + hh) * sy)))
    return slice(y0, y1), slice(x0, x1)


def distances(model, image: Image.Image, fx: float, cx: float, cy: float, boxes) -> list:
    from mapanything.utils.image import preprocess_inputs

    rgb = np.asarray(image)
    k = torch.tensor([[fx, 0, cx], [0, fx, cy], [0, 0, 1]], dtype=torch.float32)
    views = preprocess_inputs([{"img": rgb, "intrinsics": k}])
    out = model.infer(views, memory_efficient_inference=True, minibatch_size=1, use_amp=True, amp_dtype="bf16",
                      apply_mask=True, mask_edges=True)[0]
    depth = out["depth_z"][0, ..., 0].float().cpu().numpy()
    points = out["pts3d_cam"][0].float().cpu().numpy()
    h, w = depth.shape
    sx, sy = w / image.width, h / image.height
    things = []
    for box in boxes:
        rows, cols = inner(box, w, h, sx, sy)
        d, p = depth[rows, cols], points[rows, cols].reshape(-1, 3)
        ok = (d.reshape(-1) > 0.05) & np.isfinite(p).all(axis=1)
        if ok.sum() < 4:
            things.append(None)
            continue
        point = np.median(p[ok], axis=0) * SCALE
        things.append({"metres": round(float(np.linalg.norm(point)), 2), "point": [round(float(v), 3) for v in point]})
    return things


VOXEL_M = 0.03
MAX_POINTS = 40000
MAX_VIEWS = 6


def scan(model, views_in: list[dict]) -> dict:
    """Several frames joined into one room's shape, and where each boxed thing is in it."""
    from mapanything.utils.image import preprocess_inputs

    views = []
    for v in views_in:
        k = torch.tensor([[v["fx"], 0, v["cx"]], [0, v["fx"], v["cy"]], [0, 0, 1]], dtype=torch.float32)
        views.append({"img": np.asarray(v["image"]), "intrinsics": k,
                      "camera_poses": torch.tensor(v["pose"], dtype=torch.float32), "is_metric_scale": False})
    prepared = preprocess_inputs(views)
    outs = model.infer(prepared, memory_efficient_inference=True, minibatch_size=1, use_amp=True, amp_dtype="bf16",
                       apply_mask=True, mask_edges=True)
    # Only MapAnything's depth is used: each pixel's ray comes from Andy's own camera (the intrinsics given, as the
    # preprocessing scaled them) and is turned into the room by the head's angles as the motors measured them.
    # Taken whole, the joined views came out about 1.3 times too wide (the robot, 2026-10-31: a watch at -35
    # degrees read -30 and -41 from two views).
    cloud, things = [], []
    for v, out, pv in zip(views_in, outs, prepared):
        z = out["depth_z"][0, ..., 0].double().cpu().numpy()
        kk = pv["intrinsics"][0].double().cpu().numpy()
        h, w = z.shape
        u, vv = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        cam = np.stack([(u - kk[0, 2]) / kk[0, 0] * z, (vv - kk[1, 2]) / kk[1, 1] * z, z], axis=-1)
        rot = np.asarray(v["pose"], dtype=np.float64)[:3, :3]
        pts = ((cam @ rot.T) * SCALE).astype(np.float32)
        keep = out["mask"][0, ..., 0].cpu().numpy().astype(bool) & np.isfinite(pts).all(axis=-1) & (z > 0.05)
        cloud.append(pts[keep])
        sc = kk[0, 0] / v["fx"]  # the preprocessing's scale and crop, from the intrinsics it handed back
        ox, oy = kk[0, 2] - v["cx"] * sc, kk[1, 2] - v["cy"] * sc
        for b in v["boxes"]:
            l, t, r, bt = b["box"]
            rows, cols = inner((l * sc + ox, t * sc + oy, r * sc + ox, bt * sc + oy), w, h, 1.0, 1.0)
            p, ok = pts[rows, cols].reshape(-1, 3), keep[rows, cols].reshape(-1)
            if ok.sum() < 4:
                continue
            point = np.median(p[ok], axis=0)
            things.append({"label": b["label"], "score": b.get("score"), "point": [round(float(x), 3) for x in point],
                           "metres": round(float(np.linalg.norm(point)), 2)})
    pts = np.concatenate(cloud) if cloud else np.zeros((0, 3), np.float32)
    pts = pts[np.linalg.norm(pts, axis=1) < 8.0]  # the room, not a far-off guess through a window
    _, first = np.unique(np.floor(pts / VOXEL_M).astype(np.int32), axis=0, return_index=True)
    pts = pts[first]
    if len(pts) > MAX_POINTS:
        pts = pts[np.random.default_rng(0).choice(len(pts), MAX_POINTS, replace=False)]
    return {"points": base64.b64encode(pts.astype(np.float16).tobytes()).decode(), "n": int(len(pts)),
            "things": things}


def serve(model, host: str, port: int) -> None:
    lock = threading.Lock()  # one GPU, one frame at a time

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(200, {"status": "ok"} if self.path == "/health" else {"error": "not found"})

        def do_POST(self):
            if self.path not in ("/distance", "/scan"):
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= (MAX_BODY * MAX_VIEWS if self.path == "/scan" else MAX_BODY):
                return self._send(413, {"error": "body too large or empty"})
            if self.path == "/scan":
                return self._scan(n)
            try:
                req = json.loads(self.rfile.read(n))
                image = Image.open(io.BytesIO(base64.b64decode(req["image"]))).convert("RGB")
                fx, cx, cy = (float(req[k]) for k in ("fx", "cx", "cy"))
                boxes = [[float(v) for v in b][:4] for b in req["boxes"]][:16]
                if not boxes or any(len(b) != 4 for b in boxes) or fx <= 0:
                    raise ValueError
            except (ValueError, KeyError, TypeError, OSError):
                return self._send(400, {"error": "need a base64 JPEG 'image', 'fx', 'cx', 'cy' and 'boxes'"})
            start = time.monotonic()
            with lock, torch.inference_mode():
                things = distances(model, image, fx, cx, cy, boxes)
            self._send(200, {"things": things, "seconds": round(time.monotonic() - start, 3)})

        def _scan(self, n):
            try:
                req = json.loads(self.rfile.read(n))
                views = []
                for v in req["views"][:MAX_VIEWS]:
                    pose = [[float(x) for x in row][:4] for row in v["pose"]][:4]
                    boxes = [{"label": str(b["label"])[:40], "box": [float(x) for x in b["box"]][:4],
                              "score": float(b.get("score") or 0.0)} for b in v.get("boxes", [])][:24]
                    views.append({"image": Image.open(io.BytesIO(base64.b64decode(v["image"]))).convert("RGB"),
                                  "fx": float(v["fx"]), "cx": float(v["cx"]), "cy": float(v["cy"]),
                                  "pose": pose, "boxes": boxes})
                if len(views) < 2 or any(len(p) != 4 or any(len(r) != 4 for r in p) for p in (v["pose"] for v in views)):
                    raise ValueError
            except (ValueError, KeyError, TypeError, OSError):
                return self._send(400, {"error": "need 'views': 2 to 6 of image, fx, cx, cy, pose (4x4), boxes"})
            start = time.monotonic()
            try:
                with lock, torch.inference_mode():
                    out = scan(model, views)
            except Exception as e:  # noqa: BLE001 - out of GPU memory, a view MapAnything refused: say so, never hang up
                return self._send(500, {"error": f"{type(e).__name__}: {str(e)[:200]}"})
            finally:
                torch.cuda.empty_cache()
            self._send(200, {**out, "seconds": round(time.monotonic() - start, 3)})

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # no request logs: nothing about a home is written down
            pass

    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8096)
    serve(load(), "127.0.0.1", ap.parse_args().port)
