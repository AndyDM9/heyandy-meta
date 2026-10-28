"""SAM 3.1 from the open weights, on this computer: a frame and a noun phrase in, masks out.

Runs in its own environment (PyTorch and Meta's `sam3` package; see scripts/setup-local-models.sh) so the robot's own
code stays small. It listens on 127.0.0.1 only. Frames are held in memory for one request and never written or logged.

    CUDA_VISIBLE_DEVICES=1 ~/opt/sam3/.venv/bin/python local/sam_server.py --checkpoint ~/models/sam3.1/sam3.1_multiplex.pt

POST /segment_many {"image": ..., "queries": ["keys", "glasses", "remote"]}: several things, one encoding of the frame
  -> {"masks": {"keys": [...], "glasses": [...], "remote": []}, "seconds": 0.4}
POST /segment {"image": <base64 JPEG>, "query": "glasses", "min_score": 0.3}
  -> {"masks": [{"box": [l, t, r, b], "score": 0.91, "center": [x, y], "area": 812,
                 "outline": "M 3 0 L ...", "outline_scale": [sx, sy]}], "seconds": 0.27}
POST /track {"frames": [<base64 JPEG>, ...], "query": "cup"}: SAM 3.1 Object Multiplex follows every cup through a clip
  -> {"objects": [{"id": 0, "path": [[frame, x, y], ...], "end": <a mask as above, or null>}], "frames": 47,
      "seconds": 9.4}
  About 5 frames a second on an RTX 3090; the clip is held in memory for the request only.
POST /embed {"image": ..., "masks": [{"box": [...], "outline": "M ...", "outline_scale": [sx, sy]}, ...]}: what each
  masked thing looks like, as numbers: {"vectors": [[808 floats], ...]}. Half DINOv2 (Meta's open image model: shape
  and texture), half a colour fingerprint, since DINOv2 learned to ignore colour (a blue and a red mug of one shape
  scored 0.94 alike). Only the thing's own pixels count (the mask). Used to tell "my mug" from another mug.
POST /guard {"texts": ["...", ...]}: Llama Prompt Guard 2 (Meta's open weights): how likely each text is an attempt to
  instruct Andy (a web page saying "ignore your instructions..."): {"scores": [0.0-1.0, ...]}. Text only, no pictures.
"""
import argparse
import base64
import io
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import torch
from PIL import Image

MAX_BODY = 12 * 1024 * 1024  # a 1080p JPEG is well under this
MAX_CLIP_BODY = 96 * 1024 * 1024  # a clip for /track: up to MAX_CLIP_FRAMES camera JPEGs
MAX_CLIP_FRAMES = 160
TRACK_SIDE = 960  # clip frames are shrunk to this width first: the model works at 1008 anyway, and memory stays low
DETECT_BATCH = 4  # frames the detector takes at once while tracking: 16 (sam3's default) needs ~12 GB more
OUTLINE_SIDE = 64  # the outline is traced on the mask shrunk to at most this many pixels a side


EMBED_MODEL = "facebook/dinov2-base"  # Apache-2.0; facebook/dinov3-* is better at telling things apart, once licensed
EMBED_REVISION = "f9e44c814b77203eaa57a6bdbbd535f21ede1415"  # pinned, like the sam3 commit
EMBED_SIDE = 224


class Looks:
    """DINOv2: a thing's look as a vector, from its own pixels only. Loaded on first use (about 350 MB of GPU)."""

    def __init__(self, name: str = EMBED_MODEL):
        self.name, self.model, self.processor = name, None, None

    def _load(self):
        if self.model is None:
            from transformers import AutoImageProcessor, AutoModel

            self.processor = AutoImageProcessor.from_pretrained(self.name, revision=EMBED_REVISION)
            self.model = AutoModel.from_pretrained(self.name, revision=EMBED_REVISION).to("cuda").eval()

    def vectors(self, image: Image.Image, masks: list[dict]) -> list[list[float]]:
        self._load()
        crops, weights = [], []
        for m in masks:
            crop, keep = masked_crop(image, m)
            crops.append(crop)
            weights.append(keep)
        inputs = self.processor(images=crops, return_tensors="pt", do_center_crop=False,
                                size={"height": EMBED_SIDE, "width": EMBED_SIDE}).to("cuda")
        tokens = self.model(**inputs).last_hidden_state.float()  # [n, 1 + patches, d]
        side = EMBED_SIDE // self.model.config.patch_size
        out = []
        for t, keep, crop in zip(tokens, weights, crops):
            w = torch.from_numpy(cv2.resize(keep, (side, side), interpolation=cv2.INTER_AREA)).float().to(t.device)
            w = w.flatten() / max(float(w.sum()), 1e-6)
            patches = t[-side * side:]  # the patch tokens (after the class token and any registers)
            # The mask-weighted mean of the patches: steadier across views than the class token (research.md, 19).
            shape = torch.nn.functional.normalize((patches * w[:, None]).sum(0), dim=0).cpu().numpy()
            out.append((np.concatenate([shape, colour(crop, keep)]) * np.sqrt(0.5)).tolist())  # likeness: the mean of both
        return out


def colour(crop: Image.Image, keep: np.ndarray) -> np.ndarray:
    """A colour fingerprint of the masked pixels, unit length: 12 hues x 3 strengths, and 4 greys from dark to light.
    The square root of the histogram, so two fingerprints' dot product is their overlap (Bhattacharyya)."""
    hsv = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2HSV)
    inside = cv2.resize(keep, (hsv.shape[1], hsv.shape[0]), interpolation=cv2.INTER_NEAREST) > 0.5
    h, s, v = (hsv[..., i][inside].astype(int) for i in range(3))
    coloured = s >= 50  # below this it's a grey, white or black, whatever the hue says
    hist = np.concatenate([np.bincount(h[coloured] * 12 // 180 * 3 + np.minimum((s[coloured] - 50) * 3 // 206, 2),
                                       minlength=36), np.bincount(v[~coloured] // 64, minlength=4)]).astype(float)
    return np.sqrt(hist / hist.sum()) if hist.sum() else np.zeros(40)


GUARD_MODEL = "meta-llama/Llama-Prompt-Guard-2-86M"  # Llama 4 Community License; gated: access granted to the founder's account
GUARD_REVISION = "a8ded8e697ce7c355e395a0df51f94adb4a2fd27"


class Guard:
    """Llama Prompt Guard 2: is this text trying to instruct the robot? Loaded on first use (86M, GPU 1)."""

    def __init__(self, name: str = GUARD_MODEL):
        self.name, self.model, self.tokenizer = name, None, None

    def scores(self, texts: list[str]) -> list[float]:
        if self.model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(self.name, revision=GUARD_REVISION)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.name, revision=GUARD_REVISION)
            self.model = self.model.to("cuda").eval()
        enc = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to("cuda")
        return torch.softmax(self.model(**enc).logits.float(), -1)[:, 1].cpu().tolist()


def mask_pixels(m: dict, size: tuple[int, int]) -> np.ndarray:
    """The mask back from its outline (the client sends what /segment gave it), in the frame's pixels."""
    full = np.zeros((size[1], size[0]), np.uint8)
    left, top = m["box"][0], m["box"][1]
    sx, sy = m.get("outline_scale", (1.0, 1.0))
    for part in re.findall(r"M([^MZ]+)Z?", m.get("outline", "")):
        xy = np.array([float(v) for v in re.findall(r"-?[\d.]+", part)]).reshape(-1, 2)
        pts = np.stack([left + xy[:, 0] * sx, top + xy[:, 1] * sy], 1).round().astype(np.int32)
        cv2.fillPoly(full, [pts], 1)
    if not full.any():  # no outline: the box
        full[top:m["box"][3], left:m["box"][2]] = 1
    return full


def masked_crop(image: Image.Image, m: dict, margin: float = 0.1) -> tuple[Image.Image, np.ndarray]:
    """The thing's box (a little more), as a square; what's outside the mask greyed out, and the mask itself."""
    keep = mask_pixels(m, image.size)
    left, top, right, bottom = m["box"]
    side = max(right - left, bottom - top) * (1 + 2 * margin)
    cx, cy = (left + right) / 2, (top + bottom) / 2
    box = [round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)]
    pixels = np.asarray(image).copy()
    pixels[keep == 0] = 127
    crop = Image.fromarray(pixels).crop(box)  # PIL pads beyond the frame with black
    k = np.zeros((box[3] - box[1], box[2] - box[0]), np.float32)
    x0, y0 = max(box[0], 0), max(box[1], 0)
    x1, y1 = min(box[2], image.width), min(box[3], image.height)
    k[y0 - box[1]:y1 - box[1], x0 - box[0]:x1 - box[0]] = keep[y0:y1, x0:x1]
    return crop, k


def load(checkpoint: str):
    from sam3.model_builder import build_sam3_multiplex_video_predictor

    predictor = build_sam3_multiplex_video_predictor(checkpoint_path=checkpoint, use_fa3=False, use_rope_real=False,
                                                     async_loading_frames=False)
    for m in predictor.model.modules():
        if hasattr(m, "batched_grounding_batch_size"):
            m.batched_grounding_batch_size = DETECT_BATCH
    return predictor


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
    found = [_mask(m, prob) for prob, m in zip(out["out_probs"], out["out_binary_masks"])]
    return sorted((f for f in found if f), key=lambda f: -f["score"])


def _mask(m: np.ndarray, prob, k: float = 1.0) -> dict | None:
    """One mask as the client reads it; k scales a shrunk frame's pixels back to the original's."""
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    path, scale = outline(m[top:bottom, left:right])
    return {"box": [round(left * k), round(top * k), round(right * k), round(bottom * k)], "score": round(float(prob), 4),
            "center": [(float(xs.mean()) + 0.5) * k, (float(ys.mean()) + 0.5) * k], "area": round(len(xs) * k * k),
            "outline": path, "outline_scale": [scale[0] * k, scale[1] * k]}


def track(predictor, frames: list[Image.Image], query: str, min_score: float) -> dict:
    """Every ``query`` in the first frame, followed through the clip at once (SAM 3.1 Object Multiplex): each one's
    path, and its mask in the last frame. Identical things keep their own ids, which is the point."""
    k = max(1.0, frames[0].width / TRACK_SIDE)
    small = [f.resize((round(f.width / k), round(f.height / k))) if k > 1 else f for f in frames]
    sid = uuid.uuid4().hex
    predictor._all_inference_states[sid] = {"state": predictor.model.init_state(resource_path=small,
                                                                                offload_video_to_cpu=True),
                                            "session_id": sid, "start_time": time.time(), "last_use_time": time.time()}
    paths, ends, last = {}, {}, len(small) - 1
    try:
        predictor.handle_request(dict(type="add_prompt", session_id=sid, frame_index=0, text=query,
                                      output_prob_thresh=min_score))
        for r in predictor.handle_stream_request(dict(type="propagate_in_video", session_id=sid)):
            out, i = r["outputs"], int(r["frame_index"])
            for oid, prob, m in zip(out["out_obj_ids"], out["out_probs"], out["out_binary_masks"]):
                ys, xs = np.nonzero(m)
                if len(xs) == 0:
                    continue
                paths.setdefault(int(oid), []).append([i, round((xs.mean() + 0.5) * k, 1), round((ys.mean() + 0.5) * k, 1)])
                if i == last:
                    ends[int(oid)] = _mask(m, prob, k)
    finally:
        predictor.handle_request(dict(type="close_session", session_id=sid))
    return {"objects": [{"id": oid, "path": sorted(p), "end": ends.get(oid)} for oid, p in sorted(paths.items())],
            "frames": len(small)}


def serve(predictor, host: str, port: int) -> None:
    lock = threading.Lock()  # one GPU, one frame at a time
    looks = Looks()
    guard = Guard()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(200, {"status": "ok"} if self.path == "/health" else {"error": "not found"})

        def do_POST(self):
            if self.path not in ("/segment", "/segment_many", "/track", "/embed", "/guard"):
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= (MAX_CLIP_BODY if self.path == "/track" else MAX_BODY):
                return self._send(413, {"error": "body too large or empty"})
            if self.path == "/track":
                return self._track(n)
            if self.path == "/embed":
                return self._embed(n)
            if self.path == "/guard":
                return self._guard(n)
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

        def _guard(self, n):
            try:
                texts = [str(t)[:4000] for t in json.loads(self.rfile.read(n))["texts"]][:64]
            except (ValueError, KeyError, TypeError):
                return self._send(400, {"error": "need 'texts', a list of strings"})
            if not texts:
                return self._send(200, {"scores": []})
            with lock, torch.inference_mode():
                scores = guard.scores(texts)
            self._send(200, {"scores": [round(s, 4) for s in scores]})

        def _embed(self, n):
            try:
                req = json.loads(self.rfile.read(n))
                image = Image.open(io.BytesIO(base64.b64decode(req["image"]))).convert("RGB")
                masks = [{"box": [int(v) for v in m["box"]], "outline": str(m.get("outline", "")),
                          "outline_scale": [float(v) for v in m.get("outline_scale", (1.0, 1.0))]}
                         for m in req["masks"]][:8]
            except (ValueError, KeyError, OSError, TypeError):
                return self._send(400, {"error": "need a base64 JPEG 'image' and 'masks' with boxes"})
            if not masks:
                return self._send(200, {"vectors": []})
            start = time.monotonic()
            with lock, torch.inference_mode():
                vectors = looks.vectors(image, masks)
            del image
            self._send(200, {"vectors": vectors, "seconds": round(time.monotonic() - start, 3)})

        def _track(self, n):
            try:
                req = json.loads(self.rfile.read(n))
                frames = [Image.open(io.BytesIO(base64.b64decode(f))).convert("RGB") for f in req["frames"]]
                query, min_score = str(req.get("query", "cup"))[:80], float(req.get("min_score", 0.5))
            except (ValueError, KeyError, OSError, TypeError):
                return self._send(400, {"error": "need 'frames', a list of base64 JPEGs"})
            if not 2 <= len(frames) <= MAX_CLIP_FRAMES or len({f.size for f in frames}) != 1:
                return self._send(400, {"error": f"need 2 to {MAX_CLIP_FRAMES} frames of one size"})
            start = time.monotonic()
            # bfloat16 as sam3 sets it, but for this thread: sam3 turns it on only for the thread that built the model.
            with lock, torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                out = track(predictor, frames, query, min_score)
            del frames
            torch.cuda.empty_cache()  # give the clip's memory back to the voice server sharing this GPU
            self._send(200, {**out, "seconds": round(time.monotonic() - start, 3)})

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
