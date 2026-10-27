"""The voice server on this computer (local/voice_server.py): Omnilingual ASR in, Kokoro-82M out."""
import json
import urllib.error
import urllib.request

import numpy as np

from ..models.common import is_local
from ..models.sam_local import LocalUnavailable, NotLocal


class LocalVoice:
    def __init__(self, endpoint: str = "http://127.0.0.1:8092", voice: str = "am_michael", timeout: float = 10.0):
        if not is_local(endpoint):
            raise NotLocal(f"speech stays on this computer or the home network, not {endpoint}")
        self.endpoint, self.voice, self.timeout = endpoint.rstrip("/"), voice, timeout

    def _post(self, path: str, data: bytes, headers: dict):
        try:
            return urllib.request.urlopen(urllib.request.Request(self.endpoint + path, data, headers), timeout=self.timeout)
        except (urllib.error.URLError, TimeoutError) as e:
            raise LocalUnavailable(f"voice server at {self.endpoint}: {e}") from e

    def transcribe(self, samples: np.ndarray, rate: int = 16000) -> str:
        data = np.asarray(samples, dtype="<f4").tobytes()
        with self._post("/transcribe", data, {"X-Sample-Rate": str(rate)}) as r:
            return json.load(r)["text"]

    def speak(self, text: str, rate: int = 16000) -> np.ndarray:
        body = json.dumps({"text": text, "voice": self.voice, "rate": rate}).encode()
        with self._post("/speak", body, {"Content-Type": "application/json"}) as r:
            return np.frombuffer(r.read(), dtype="<f4").copy()
