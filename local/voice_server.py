"""Hearing and speaking on this computer: Meta's Omnilingual ASR in, Kokoro-82M out (both Apache-2.0).

Runs in its own environment (scripts/setup-local-models.sh) on GPU 1 beside SAM 3.1, and listens on 127.0.0.1 only.
Audio is held in memory for one request; nothing is written or logged.

    CUDA_VISIBLE_DEVICES=1 ~/opt/voice/.venv/bin/python local/voice_server.py

POST /transcribe  body: float32 little-endian mono samples; header X-Sample-Rate (default 16000)
  -> {"text": "where are my glasses", "seconds": 0.04}
POST /speak       {"text": "I see your glasses.", "voice": "am_michael", "rate": 16000}
  -> body: float32 little-endian mono samples at "rate" (default 24000, Kokoro's own); headers X-Sample-Rate, X-Seconds
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import torch
import torchaudio

MAX_SECONDS = 30  # Omnilingual ASR's CTC models take clips under 40 s
VOICE = "am_michael"
LANG = "eng_Latn"


def louder(audio: np.ndarray, target_db: float = -18.0) -> np.ndarray:
    """Kokoro speaks at about -28 dBFS: bring it up to target_db (RMS), with a soft limiter so peaks never clip."""
    rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
    if rms < 1e-5:
        return audio
    gain = min(10 ** (target_db / 20) / rms, 8.0)
    return (0.95 * np.tanh(gain * audio / 0.95)).astype(np.float32)


def load(asr_card: str):
    from kokoro import KPipeline
    from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline

    return ASRInferencePipeline(model_card=asr_card, device="cuda"), KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")


def serve(asr, tts, asr_card: str, host: str, port: int) -> None:
    lock = threading.Lock()  # one GPU

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._json(200, {"status": "ok"} if self.path == "/health" else {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if self.path == "/transcribe":
                rate = int(self.headers.get("X-Sample-Rate") or 16000)
                if not 0 < n <= MAX_SECONDS * rate * 4 or n % 4:
                    return self._json(413, {"error": f"send 0 to {MAX_SECONDS} s of float32 samples"})
                audio = torch.from_numpy(np.frombuffer(self.rfile.read(n), dtype="<f4").copy())
                if rate != 16000:
                    audio = torchaudio.functional.resample(audio, rate, 16000)
                peak = float(audio.abs().max()) if audio.numel() else 0.0
                if peak > 1e-4:
                    audio = audio * (0.9 / peak)  # a voice across the room arrives quiet; even it out
                start = time.monotonic()
                with lock:
                    kw = {"lang": [LANG]} if "LLM" in asr_card else {}  # CTC models can't be told the language
                    text = asr.transcribe([{"waveform": audio.numpy(), "sample_rate": 16000}], batch_size=1, **kw)[0]
                return self._json(200, {"text": text.strip(), "seconds": round(time.monotonic() - start, 3)})
            if self.path == "/speak":
                try:
                    req = json.loads(self.rfile.read(min(n, 8192)))
                    text, voice = str(req["text"])[:600], str(req.get("voice") or VOICE)
                    rate = int(req.get("rate") or 24000)
                except (ValueError, KeyError):
                    return self._json(400, {"error": "need 'text'"})
                start = time.monotonic()
                try:
                    with lock:
                        parts = [np.asarray(a, dtype=np.float32) for _, _, a in tts(text, voice=voice, speed=1.0)]
                except Exception as e:  # noqa: BLE001 - e.g. a voice that isn't downloaded; say so, don't drop the line
                    return self._json(500, {"error": f"{type(e).__name__}: {e}"[:300]})
                audio = np.concatenate(parts) if parts else np.zeros(0, np.float32)
                if rate != 24000 and audio.size:
                    audio = torchaudio.functional.resample(torch.from_numpy(audio), 24000, rate).numpy()
                audio = louder(audio)
                data = audio.astype("<f4").tobytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Sample-Rate", str(rate))
                self.send_header("X-Seconds", f"{time.monotonic() - start:.3f}")
                self.end_headers()
                return self.wfile.write(data)
            self._json(404, {"error": "not found"})

        def _json(self, code, body):
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
    ap.add_argument("--asr", default="omniASR_LLM_1B_v2")  # told the language; see research.md section 10
    ap.add_argument("--port", type=int, default=8092)
    args = ap.parse_args()
    serve(*load(args.asr), args.asr, "127.0.0.1", args.port)
