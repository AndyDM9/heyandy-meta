"""Homes, on the robot: "my watch lives here", then "is everything home?" with one thing away from its home.

The app is built as the service builds it (the voice too) with a scratch memory, so the home's own isn't touched.
Things on the table get their homes where Andy sees them; one more (--away) is given a home where it isn't (60
degrees to the left, "the bowl by the door"), as if it had been left out. The check should find the others home, and
point at the away one, then at its home. Only words and numbers are kept.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.home --homes watch,cup --away keys
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
    ap.add_argument("--homes", default="watch,cup")
    ap.add_argument("--away", default="keys")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    andy = build(argparse.Namespace(
        data=tempfile.mkdtemp(prefix="andy-home-"), robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    andy.describe_in_background = False  # the home's words before the check, for the record
    spoken, points = [], []
    say, point = andy.body.say, andy.body.point
    andy.body.say = lambda text: (spoken.append(text), say(text))
    andy.body.point = lambda yaw, pitch: (points.append([round(yaw, 1), round(pitch, 1)]), point(yaw, pitch))
    started, set_words = time.monotonic(), {}
    for thing in args.homes.split(","):
        with andy.lock:
            set_words[thing] = andy.hear(f"my {thing} lives here")  # hear() says its answer
        print(thing, "->", set_words[thing])
    away = args.away
    andy.places.watch(away)
    andy.places.set_home(away, 60.0, 20.0, None, "in the bowl by the door")
    andy.body.look(0, 0)
    spoken.clear(), points.clear()
    check_started = time.monotonic()
    with andy.lock:
        last = andy.hear("is everything home?")
    check_s = time.monotonic() - check_started
    andy.body.look(0, 0)
    rows = andy.screen.snapshot()["homes"]["rows"] if andy.screen.snapshot().get("homes") else None
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "set": set_words, "homes": andy.places.homes(),
              "check_said": spoken, "last": last, "points_in_check": points, "rows": rows, "check_seconds": round(check_s, 1),
              "total_seconds": round(time.monotonic() - started, 1)}
    print(json.dumps(result, indent=1))
    out = Path(args.out) / f"home-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
