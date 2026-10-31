"""Guide my hand, on the robot: Andy finds a thing, then watches for a hand and talks it in (companion/guide.py).

With nobody at the table it measures what matters first: that no hand is made up from the table (a keyboard, a
watch strap, a glove) and how many frames a second the guide gets. With --person, reach for the thing: the words are
printed and the notes play on the robot's speaker (the full app says the words too).

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.guide --thing cup --seconds 20
    systemctl --user start heyandy-app

The frames go to SAM 3.1 on this computer and nowhere else; only numbers and words are kept.
"""
import argparse
import json
import time
from pathlib import Path

from heyandy_meta.companion.guide import HAND, HAND_SCORE, guide, height_above
from heyandy_meta.finder.perspective import on_plan
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.sam_local import LocalSam31


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thing", default="cup")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--person", action="store_true", help="someone reaches for the thing")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    from heyandy_meta.robot.reachy_mini import ReachyBody

    body, sam = ReachyBody(), LocalSam31()
    finder = Finder(body, sam, verify=False)
    body.look(0, 0)
    found = finder.find(args.thing)
    if not found:
        print(f"{args.thing}: not found")
        return
    body.point(found.yaw, found.pitch)
    print(f"{args.thing}: at {found.yaw:.1f}, {found.pitch:.1f}")
    hands, frames, said = [], [], []

    class Watching:  # SAM 3.1 as the guide uses it, with every hand it reports kept, even the unsure ones
        def find_many(self, frame, queries):
            t = time.monotonic()
            out = sam.find_many(frame, queries)
            frames.append(round(time.monotonic() - t, 3))
            hands.append([round(m.score or 0.0, 2) for m in out.get(HAND, [])])
            return out

    def say(words):
        said.append(words)
        print("  say:", words)

    started = time.monotonic()
    r = guide(body, Watching(), args.thing, (found.yaw, found.pitch), height_above(found.pitch, None), on_plan(0.0, 0.0, 1.0),
              say, body.chime, lambda *a: None, lambda: False, args.seconds, cam=finder._cam)
    took = time.monotonic() - started
    body.look(0, 0)
    made_up = sum(1 for h in hands if any(s >= HAND_SCORE for s in h))
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "thing": args.thing, "person": args.person, "why": r.why,
              "frames": r.frames, "per_second": round(r.frames / took, 2), "sam_s_median": sorted(frames)[len(frames) // 2],
              "frames_with_a_hand": made_up, "hand_scores": hands, "closest_m": r.closest, "said": said}
    print(json.dumps({k: v for k, v in result.items() if k != "hand_scores"}, indent=1))
    out = Path(args.out) / f"guide-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
