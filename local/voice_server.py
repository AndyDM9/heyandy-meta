"""Hearing and speaking on this computer: Meta's Omnilingual ASR in (Apache-2.0); Meta's SeamlessM4T v2 out (CC-BY-NC 4.0).

Every model Andy runs must be Meta's (the hackathon's rule, docs/rules.md), and Meta's Model API has no voice, so Andy
speaks with Meta's open text-to-speech. SeamlessM4T v2's speech part (facebook/seamless-m4t-v2-large, 1.7B parameters,
0.2 to 0.3 s a sentence in fp16) is clear: Omnilingual ASR misheard 9% of its words on Andy's own lines, against 23 to
28% for MMS-TTS (facebook/mms-tts-eng and -spa, 36M parameters), which stays as the fallback. MMS reads lowercase words
only, so for it heyandy_meta/voice/spoken.py cuts the text into phrases and puts the pauses back; for both, numbers,
times and units become words first. Seamless runs on the second GPU this process sees (--tts-device), beside Glimmer.

Runs in its own environment (scripts/setup-local-models.sh) on GPU 1 beside SAM 3.1, and listens on 127.0.0.1 only.
Audio is held in memory for one request; nothing is written or logged.

    CUDA_VISIBLE_DEVICES=1 ~/opt/voice/.venv/bin/python local/voice_server.py

POST /transcribe  body: float32 little-endian mono samples; headers X-Sample-Rate (default 16000), X-Language
                  (Omnilingual ASR's code, default eng_Latn; spa_Latn for Spanish)
  -> {"text": "where are my glasses", "seconds": 0.04}
POST /speak       {"text": "I see your glasses.", "voice": "eng", "rate": 16000, "speed": 1.0, "loudness": -21}
                  The voice is the language, eng or spa (the old mms-eng and mms-spa still work).
  -> body: float32 little-endian mono samples at "rate" (default 16000, MMS-TTS's own); headers X-Sample-Rate, X-Seconds
"""
import argparse
import json
import re
import sys
import threading
from pathlib import Path
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import torch
import torchaudio

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from heyandy_meta.voice.spoken import phrases, words  # noqa: E402

MAX_SECONDS = 30  # Omnilingual ASR's CTC models take clips under 40 s
VOICE = "eng"
TTS_RATE = 16000  # both Seamless and MMS-TTS speak at 16 kHz
SEAMLESS = "facebook/seamless-m4t-v2-large"
# Its tokenizer, saved once by scripts/setup-local-models.sh: loaded offline from the hub cache, it turned every word into
# "unknown" and Seamless spoke noise (2026-10-30); from this copy it's right.
PROCESSOR = Path.home() / "models" / "seamless-m4t-v2-processor"
LANG = "eng_Latn"


def louder(audio: np.ndarray, target_db: float = -24.0) -> np.ndarray:
    """As loud as the setting asks, never clipped: the peak at 0.89 at -24 dB (the level the founder picked, by ear,
    on the robot's speaker, Oct 30), quieter below it. A soft clipper used to lift quiet speech up to 8 times, which
    blurred the consonants on the robot's small speaker."""
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    if peak < 1e-5:
        return audio
    return (audio * min(0.89, 0.89 * 10 ** ((target_db + 24.0) / 20)) / peak).astype(np.float32)


def clearer(audio: np.ndarray, speed: float = 1.0) -> np.ndarray:
    """For the robot's small speaker (picked by ear on the robot, Oct 30): a little slower, no rumble under 120 Hz,
    and the consonants brought forward (6 dB around 3 kHz)."""
    audio = stretch(audio.astype(np.float32), 0.92 * speed)
    t = torchaudio.functional.highpass_biquad(torch.from_numpy(audio).unsqueeze(0), TTS_RATE, 120.0)
    return torchaudio.functional.equalizer_biquad(t, TTS_RATE, 3000.0, 6.0, 0.8).squeeze(0).numpy().astype(np.float32)


def stretch(audio: np.ndarray, speed: float) -> np.ndarray:
    """Faster or slower without changing the pitch (a phase vocoder): Seamless has no speaking rate of its own."""
    if abs(speed - 1.0) < 0.03 or audio.size < 2048:
        return audio
    n_fft, hop = 512, 128
    window = torch.hann_window(n_fft)
    spec = torch.stft(torch.from_numpy(audio), n_fft, hop, window=window, return_complex=True)
    advance = torch.linspace(0, np.pi * hop, n_fft // 2 + 1)[..., None]
    out = torchaudio.functional.phase_vocoder(spec, speed, advance)
    return torch.istft(out, n_fft, hop, window=window).numpy().astype(np.float32)


def load(asr_card: str, tts_device: str = "cuda:1", speaker: int = 0, voice_model: str = "mms"):
    from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
    from transformers import AutoTokenizer, VitsModel

    voices = {}
    seamless = None
    try:  # only when asked for (--voice-model seamless); if it can't load, MMS-TTS speaks instead
        if voice_model != "seamless":
            raise LookupError("MMS-TTS was asked for")
        from transformers import AutoProcessor, SeamlessM4Tv2ForTextToSpeech

        seamless = (AutoProcessor.from_pretrained(PROCESSOR if PROCESSOR.exists() else SEAMLESS),
                    SeamlessM4Tv2ForTextToSpeech.from_pretrained(
            SEAMLESS, dtype=torch.float16).to(tts_device).eval())
    except LookupError:
        pass
    except Exception as e:  # noqa: BLE001 - say so in the log, and speak with MMS
        print(f"SeamlessM4T v2 didn't load ({type(e).__name__}: {e}); speaking with MMS-TTS", flush=True)

    def mms(text, lang, speed):
        if lang not in voices:
            name = f"facebook/mms-tts-{lang}"
            voices[lang] = (AutoTokenizer.from_pretrained(name), VitsModel.from_pretrained(name).to("cuda").eval())
        tok, model = voices[lang]
        model.speaking_rate = 1.0  # the pace is set after, with the rest of what makes it clearer
        out = []
        for said, pause in phrases(text, "es" if lang == "spa" else "en"):
            out.append(model(**tok(said, return_tensors="pt").to("cuda")).waveform[0].float().cpu().numpy())
            out.append(np.zeros(int(pause * TTS_RATE), np.float32))
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    def tts(text, voice, speed):
        """Andy's voice in the language asked for (eng or spa): 16 kHz samples."""
        lang = "spa" if voice.endswith("spa") else "eng"
        with torch.inference_mode():
            if seamless is None or voice.startswith("mms"):
                return clearer(mms(text, lang, speed), speed)
            processor, model = seamless
            said = words(text, "es" if lang == "spa" else "en")
            inputs = processor(text=said, src_lang=lang, return_tensors="pt").to(tts_device)
            with torch.cuda.device(tts_device):  # each request is a new thread, whose current GPU would be the first
                audio = model.generate(**inputs, tgt_lang=lang, speaker_id=speaker)[0].float().cpu().numpy().squeeze()
        return clearer(audio, speed)

    return ASRInferencePipeline(model_card=asr_card, device="cuda:0"), tts


def serve(asr, tts, asr_card: str, host: str, port: int) -> None:
    lock = threading.Lock()  # one GPU

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._json(200, {"status": "ok"} if self.path == "/health" else {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if self.path == "/transcribe":
                rate = int(self.headers.get("X-Sample-Rate") or 16000)
                lang = self.headers.get("X-Language") or LANG
                if not re.fullmatch(r"[a-z]{3}_[A-Z][a-z]{3}", lang):
                    return self._json(400, {"error": "X-Language: a code like eng_Latn or spa_Latn"})
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
                    kw = {"lang": [lang]} if "LLM" in asr_card else {}  # CTC models can't be told the language
                    text = asr.transcribe([{"waveform": audio.numpy(), "sample_rate": 16000}], batch_size=1, **kw)[0]
                return self._json(200, {"text": text.strip(), "seconds": round(time.monotonic() - start, 3)})
            if self.path == "/speak":
                try:
                    req = json.loads(self.rfile.read(min(n, 8192)))
                    text, voice = str(req["text"])[:600], str(req.get("voice") or VOICE)
                    rate = int(req.get("rate") or TTS_RATE)
                    speed = min(1.3, max(0.7, float(req.get("speed") or 1.0)))
                    loudness = min(-12.0, max(-30.0, float(req.get("loudness") or -21.0)))
                except (ValueError, KeyError):
                    return self._json(400, {"error": "need 'text'"})
                start = time.monotonic()
                try:
                    with lock:
                        audio = tts(text, voice=voice, speed=speed)
                except Exception as e:  # noqa: BLE001 - e.g. a voice that isn't downloaded; say so, don't drop the line
                    return self._json(500, {"error": f"{type(e).__name__}: {e}"[:300]})
                if rate != TTS_RATE and audio.size:
                    audio = torchaudio.functional.resample(torch.from_numpy(audio), TTS_RATE, rate).numpy()
                audio = louder(audio, loudness)  # clipped never; the founder's setting decides the level
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
    ap.add_argument("--tts-device", default="cuda:1", help="where SeamlessM4T v2 runs (this process sees GPU 1, then 0)")
    ap.add_argument("--speaker", type=int, default=0, help="which of SeamlessM4T v2's voices")
    ap.add_argument("--voice-model", choices=["mms", "seamless"], default="mms",
                    help="Meta's MMS-TTS (the founder's pick on the robot's speaker) or SeamlessM4T v2")
    args = ap.parse_args()
    serve(*load(args.asr, args.tts_device, args.speaker, args.voice_model), args.asr, "127.0.0.1", args.port)
