"""What it's told, on the robot: "I'm putting my passport in the top drawer of the desk", then "where's my passport?".

The first ask must be answered from the words at once, the head not moving (no camera sees into a drawer); asked
again, Andy looks around the room, and when it doesn't find it there, says what it was told. The app is built as the
service builds it (the voice too) with a scratch memory. Only words, numbers and the head's moves are kept.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 uv run python -m evals.told
    systemctl --user start heyandy-app
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from heyandy_meta.__main__ import build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    andy = build(argparse.Namespace(
        data=tempfile.mkdtemp(prefix="andy-told-"), robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    moves = []
    look, capture = andy.body.look, andy.body.capture
    andy.body.look = lambda *a, **k: (moves.append("look"), look(*a, **k))[1]
    andy.body.capture = lambda: (moves.append("capture"), capture())[1]
    turns = []
    for said in ("Hey Andy, I'm putting my passport in the top drawer of the desk", "Where's my passport?",
                 "Where's my passport?"):
        moves.clear()
        started = time.monotonic()
        with andy.lock:
            words = andy.hear(said)
        turns.append({"said": said, "andy": words, "seconds": round(time.monotonic() - started, 1),
                      "looks": moves.count("look"), "frames": moves.count("capture")})
        print(turns[-1])
    andy.body.look(0, 0)
    out = Path(args.out) / f"told-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "turns": turns}, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
