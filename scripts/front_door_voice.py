"""Andy's own voice for the public demo's front door: the line it says before its first answer on the robot ("I'm
Andy, an AI robot."), in each of its fifteen languages, made by its voice service (Meta's SeamlessM4T v2 on this
computer, local/voice_server.py) exactly as the robot says it, and kept as small MP3s with the page.

The words are Andy's hand-written ones (companion/language.py and companion/safety.py DISCLOSURE): nothing is
translated for the page. A manifest beside them keeps each clip's words, voice, length and SHA-256, so a test knows
each sounds like what the page shows. Made once, here (the voice service runs on the robot's computer); the Space's
build copies them.

    uv run python scripts/front_door_voice.py        # -> heyandy_meta/screen/voice/: <language>.mp3, voice.json,
                                                     #    and the story's chapters, story-NN.mp3 and story.json
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


# The story (page.html STORY), told by Andy in its own voice: each chapter's line in the first person, saying no more than
# the line and its proof under it (a chapter not yet tried on the robot says so on screen, as before). By chapter title.
STORY = {
    "Andy, on the table": "This is me, on the table. I turn to your voice, look around the room, and point.",
    "Meet Andy": "Hi, I'm Andy. I find what you've lost, and point at it. This is the TV beside me.",
    "You ask": "You ask: Hey Andy, where's my mug? I look around the room, and SAM 3.1 outlines everything that could be it.",
    "It finds it": "There it is. I point, check my aim with my own camera, and MapAnything tells me how far away it is.",
    "It doesn't give up": "Not found? I keep looking while you get on with your day, and tell you the moment it turns up.",
    "It guides your hand": "Can't see well? I watch your hand and talk it onto the thing, from your side: toward you, and right.",
    "It knows your room": "Five looks, and I know your room in 3D, your things pinned. Its shape only, never a picture.",
    "Identical cups, told apart": "Identical cups? SAM 3.1 Object Multiplex follows every one of them through the shuffle.",
    "Before you go": "Going out? I point at what you'd leave behind, and Muse Spark checks whether you'll need an umbrella.",
    "Your language": "I hear and speak fifteen languages. Muse Glimmer translates, on the computer beside me.",
    "What it never does": "And what I never do: your pictures and voice stay home, I give no health advice, and I say I'm an AI.",
}


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
    told = {}
    speaker = LocalVoice("http://127.0.0.1:8092", voice="eng")
    for n, (title, text) in enumerate(STORY.items()):
        samples = speaker.speak(text, rate=RATE)
        path = OUT / f"story-{n:02d}.mp3"
        seconds = mp3(samples, path)
        heard = round(heard_back(text, speaker.transcribe(samples, RATE, language="eng_Latn")), 2)
        told[title] = {"text": text, "seconds": seconds, "file": f"voice/story-{n:02d}.mp3", "heard back": heard,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"story {n:02d}: {seconds:.2f} s, heard back {heard:.2f}  {title}")
    (OUT / "story.json").write_text(json.dumps({"what": "The story, told by Andy in its own voice (SeamlessM4T v2)",
                                                "chapters": told}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
