"""SAM 3.1 from the open weights, on this computer: a frame and a noun phrase in, masks out.

Runs in its own environment (PyTorch and Meta's `sam3` package; see scripts/setup-local-models.sh) so the robot's own
code stays small. It listens on 127.0.0.1 only. Frames are held in memory for one request and never written or logged.

    CUDA_VISIBLE_DEVICES=1 ~/opt/sam3/.venv/bin/python local/sam_server.py --checkpoint ~/models/sam3.1/sam3.1_multiplex.pt

POST /segment_many {"image": ..., "queries": ["keys", "glasses", "remote"]}: several things, one encoding of the frame
  -> {"masks": {"keys": [...], "glasses": [...], "remote": []}, "seconds": 0.4}
POST /segment {"image": <base64 JPEG>, "query": "glasses", "min_score": 0.3}
  -> {"masks": [{"box": [l, t, r, b], "score": 0.91, "center": [x, y], "area": 812,
                 "outline": "M 3 0 L ...", "outline_scale": [sx, sy]}], "seconds": 0.27}
"""
import argparse
import base64
import io
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import torch
from PIL import Image

MAX_BODY = 12 * 1024 * 1024  # a 1080p JPEG is well under this
OUTLINE_SIDE = 64  # the outline is traced on the mask shrunk to at most this many pixels a side


def load(checkpoint: str):
    from sam3.model_builder import build_sam3_multiplex_video_predictor

    return build_sam3_multiplex_video_predictor(checkpoint_path=checkpoint, use_fa3=False, use_rope_real=False,
                                                async_loading_frames=False)


def outline(mask: np.ndarray) -> tuple[str, tuple[float, float]]:
    """An SVG path around the mask, in a shrunk copy's pixels, and the scale back to the box's pixels."""
    h, w = mask.shape
    k = max(h, w) / OUTLINE_SIDE if max(h, w) > OUTLINE_SIDE else 1.0
    small = cv2.resize(mask.astype(np.uint8), (max(1, round(w / k)), max(1, round(h / k))),
                       interpolation=cv2.INTER_AREA if k > 1 else cv2.INTER_NEAREST)
    contours, _ = cv2.findContours(small, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    parts = []
    for c in contours:
        c = cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2)
        if len(c) >= 3:
            parts.append("M " + " L ".join(f"{x} {y}" for x, y in c) + " Z")
    return " ".join(parts), (w / small.shape[1], h / small.shape[0])


def masks(predictor, image: Image.Image, query: str, min_score: float) -> list[dict]:
    return masks_many(predictor, image, [query], min_score)[query]


def masks_many(predictor, image: Image.Image, queries: list[str], min_score: float) -> dict[str, list[dict]]:
    """Several things in one frame: one session, so the image is encoded once and each prompt reuses it."""
    sid = uuid.uuid4().hex
    # Registered directly: start_session in sam3 at f1647e8 passes offload_state_to_cpu, which the 3.1 model rejects.
    predictor._all_inference_states[sid] = {"state": predictor.model.init_state(resource_path=[image]),
                                            "session_id": sid, "start_time": time.time(), "last_use_time": time.time()}
    found = {}
    try:
        for q in queries:
            predictor.handle_request(dict(type="reset_session", session_id=sid))
            out = predictor.handle_request(dict(type="add_prompt", session_id=sid, frame_index=0, text=q,
                                                output_prob_thresh=min_score))["outputs"]
            found[q] = _masks(out)
    finally:
        predictor.handle_request(dict(type="close_session", session_id=sid))
    return found


def _masks(out) -> list[dict]:
    found = []
    for prob, m in zip(out["out_probs"], out["out_binary_masks"]):
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            continue
        left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        path, scale = outline(m[top:bottom, left:right])
        found.append({"box": [left, top, right, bottom], "score": round(float(prob), 4),
                      "center": [float(xs.mean()) + 0.5, float(ys.mean()) + 0.5], "area": int(len(xs)),
                      "outline": path, "outline_scale": list(scale)})
    return sorted(found, key=lambda f: -f["score"])


def serve(predictor, host: str, port: int) -> None:
    lock = threading.Lock()  # one GPU, one frame at a time

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(200, {"status": "ok"} if self.path == "/health" else {"error": "not found"})

        def do_POST(self):
            if self.path not in ("/segment", "/segment_many"):
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= MAX_BODY:
                return self._send(413, {"error": "body too large or empty"})
            try:
                req = json.loads(self.rfile.read(n))
                image = Image.open(io.BytesIO(base64.b64decode(req["image"]))).convert("RGB")
                queries = [str(q)[:80] for q in (req["queries"] if self.path == "/segment_many" else [req["query"]])][:8]
                min_score = float(req.get("min_score", 0.3))
            except (ValueError, KeyError, OSError):
                return self._send(400, {"error": "need a base64 JPEG 'image' and a 'query'"})
            start = time.monotonic()
            with lock, torch.inference_mode():
                found = masks_many(predictor, image, queries, min_score)
            del image
            seconds = round(time.monotonic() - start, 3)
            if self.path == "/segment":
                return self._send(200, {"masks": found[queries[0]], "seconds": seconds})
            self._send(200, {"masks": found, "seconds": seconds})

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # no request logs
            pass

    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--port", type=int, default=8090)
    args = ap.parse_args()
    serve(load(args.checkpoint), "127.0.0.1", args.port)
