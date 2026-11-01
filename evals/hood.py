"""Under the hood, on the robot: a few real turns timed stage by stage, kept as the public demo's sample.

Each question is spoken in Andy's own voice (SeamlessM4T v2) and heard by Omnilingual ASR, as the voice loop hears a
person (the hearing is timed from the end of the words); Andy plays its "heard" note and takes the turn on the robot.
The timings (numbers and models' names only) go to evals/results and, with --sample, to the public demo's sample.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 uv run python -m evals.hood --sample
    systemctl --user start heyandy-app
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from heyandy_meta.__main__ import build

ASK = ("What time is it?", "Are you OK?", "Where is my cup?")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="keep it as the public demo's sample (heyandy_meta/screen)")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    andy = build(argparse.Namespace(
        data=tempfile.mkdtemp(prefix="andy-hood-"), robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    for question in ASK:
        audio = andy.voice.speak(question, rate=16000)
        words_ended = time.monotonic()
        heard = andy.voice.transcribe(audio)
        andy.hood.heard(words_ended, time.monotonic() - words_ended)
        andy.chime("heard")
        with andy.lock:
            said = andy.hear(heard)
        print(f"{question!r} heard as {heard!r} -> {said[:90]!r}")
        time.sleep(1.0)
    andy.body.look(0, 0)
    snap = {**andy.hood.snapshot(), "services": andy._services()}
    snap["recorded"] = time.strftime("%Y-%m-%d %H:%M")
    print(json.dumps({"latest": {k: snap["latest"][k] for k in ("what", "total", "first_sound", "stages")},
                      "turns": [(t["what"], t["total"]) for t in snap["turns"]]}, indent=1))
    out = Path(args.out) / f"hood-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(snap, indent=1))
    print(f"saved {out}")
    if args.sample:
        sample = Path("heyandy_meta/screen/hood_sample.json")
        sample.write_text(json.dumps({k: v for k, v in snap.items() if k != "show_s"}, indent=1))
        print(f"and {sample}")


if __name__ == "__main__":
    main()
