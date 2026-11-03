"""Andy's own voice for the public demo's front door: the line it says before its first answer on the robot ("I'm
Andy, an AI robot."), in each of its fifteen languages, made by its voice service (Meta's SeamlessM4T v2 on this
computer, local/voice_server.py) exactly as the robot says it, and kept as small MP3s with the page.

The words are Andy's hand-written ones (companion/language.py and companion/safety.py DISCLOSURE): nothing is
translated for the page. A manifest beside them keeps each clip's words, voice, length and SHA-256, so a test knows
each sounds like what the page shows. Made once, here (the voice service runs on the robot's computer); the Space's
build copies them.

    uv run python scripts/front_door_voice.py        # -> heyandy_meta/screen/voice/<language>.mp3 and voice.json
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "heyandy_meta" / "screen" / "voice"
RATE = 16000  # what the robot's speaker is sent


def lines() -> dict[str, tuple[str, str, str]]:
    """{language: (Andy's hand-written introduction, its SeamlessM4T voice, its Omnilingual ASR language)}"""
    from heyandy_meta.companion.language import LANGUAGES
    from heyandy_meta.companion.safety import DISCLOSURE

    return {code: (lang.disclosure or DISCLOSURE, lang.voice, lang.asr) for code, lang in LANGUAGES.items()}


def mp3(samples, path: Path) -> float:
    """Mono float samples at RATE, as a small MP3; returns the seconds."""
    import numpy as np

    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "24000",
                        "-c:a", "libmp3lame", "-b:a", "40k", str(path)], check=True)
    return round(len(samples) / RATE, 2)


def main() -> None:
    from heyandy_meta.voice.local import LocalVoice

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    from evals.languages import heard_back

    for code, (text, voice, asr) in lines().items():
        speaker = LocalVoice("http://127.0.0.1:8092", voice=voice)
        samples = speaker.speak(text, rate=RATE)
        path = OUT / f"{code}.mp3"
        seconds = mp3(samples, path)
        # heard back by Andy's own ears (Omnilingual ASR, told the language): the clip says its words
        heard = round(heard_back(text, speaker.transcribe(samples, RATE, language=asr)), 2)
        manifest[code] = {"text": text, "voice": voice, "seconds": seconds, "file": f"voice/{code}.mp3",
                          "heard back": heard, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"{code}: {seconds:.2f} s, {path.stat().st_size // 1024} KB, heard back {heard:.2f}  {text}")
    (OUT / "voice.json").write_text(json.dumps({"what": __doc__.strip().splitlines()[0], "model": "SeamlessM4T v2",
                                                "clips": manifest}, ensure_ascii=False, indent=1))
    print(f"saved {len(manifest)} clips in {OUT}")


if __name__ == "__main__":
    main()
