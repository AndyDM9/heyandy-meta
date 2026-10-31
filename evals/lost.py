"""Lost and found, on the robot: Andy is told some things are lost, then looks again once (app.py _look_again).

The things given with --present are on the table (so the look should spot one, the full search confirm and point at
it, and Andy say "Good news: your watch turned up!"); --absent ones aren't anywhere (so nothing should be spotted, or
if it is, the search should turn it down in silence). The whole app is built as the service builds it, the voice
too, with a fresh memory in a scratch folder, so the home's own memory isn't touched.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.lost --present watch --absent wallet
    systemctl --user start heyandy-app

Pictures go only to SAM 3.1, MapAnything and Glimmer on this computer and are never kept; only words and numbers are
saved.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from heyandy_meta.__main__ import build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--present", default="watch")
    ap.add_argument("--absent", default="wallet")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    data = tempfile.mkdtemp(prefix="andy-lost-")
    andy = build(argparse.Namespace(
        data=data, robot=True, voice=not args.no_voice, no_cloud=True, offline=False, no_local_agent=True,
        glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094", sam="http://127.0.0.1:8090",
        voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096", voice_name="eng", home="", staged_scene=False))
    spoken = []
    say = andy.body.say
    andy.body.say = lambda text: (spoken.append(text), say(text))
    present, absent = [t for t in args.present.split(",") if t], [t for t in args.absent.split(",") if t]
    for t in present + absent:
        andy.lost.add(t)
    andy.body.look(0, 0)
    started = time.monotonic()
    with andy.lock:
        said = andy._look_again()
    took = time.monotonic() - started
    found = andy.finder.last_found
    andy.body.look(0, 0)
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "present": present, "absent": absent, "said": said,
              "everything_said": spoken, "still_looking": andy.lost.looking(), "seconds": round(took, 1),
              "pointed_at": None if found is None else {"label": found.label, "yaw": round(found.yaw, 1),
                                                        "pitch": round(found.pitch, 1), "aim_deg": found.aim_deg,
                                                        "metres": found.metres}}
    print(json.dumps(result, indent=1))
    out = Path(args.out) / f"lost-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
