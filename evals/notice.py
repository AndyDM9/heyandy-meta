"""Andy notices, measured: false alarms in a room where nothing is put down, and, with a person, the real thing.

Each clip is what the running Andy does while it keeps an eye on something (memory/notice.py): 4 s, the head held
still, V-JEPA 2 asked only where something moved. With nobody there (the default), every clip should ask little and
notice nothing. With --person, someone in front of the robot does what each prompt says (put the keys down, pick them
up, or nothing) and the clips are scored. Only numbers are kept.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.notice --clips 10              # nobody there
        uv run python -m evals.notice --person --clips 12     # someone follows the prompts
    systemctl --user start heyandy-app
"""
import argparse
import json
import random
import time
from pathlib import Path

from heyandy_meta.memory.notice import Noticer
from heyandy_meta.models.sam_local import LocalSam31


class Watching:
    """Andy's memory, played: these things watched, and where they were put down, for the scorecard."""

    def __init__(self, things):
        self.things, self.seen = list(things), []

    def watching(self):
        return self.things

    def saw(self, label, yaw, pitch, when=None, metres=None):
        self.seen.append((label, round(yaw, 1), round(pitch, 1)))
        return True

    def last_seen(self, label, now=None):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=10)
    ap.add_argument("--things", default="keys")
    ap.add_argument("--person", action="store_true", help="someone in front of the robot follows a prompt per clip")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    from heyandy_meta.robot.reachy_mini import ReachyBody

    body, sam = ReachyBody(), LocalSam31(timeout=60)
    memory = Watching(args.things.split(","))
    noticer = Noticer(body, sam, memory)
    body.look(-15, 15)
    asks = ["put", "taken", "nothing"] * (args.clips // 3 + 1)
    random.Random(5).shuffle(asks)
    clips = []
    for i in range(args.clips):
        expect = asks[i] if args.person else "nothing"
        if args.person:
            print(f"\nclip {i + 1}: in 3 s, " + {"put": f"PUT the {memory.things[0]} DOWN on the table, in view",
                                                    "taken": f"PICK the {memory.things[0]} UP", "nothing": "do NOTHING"}[expect])
            time.sleep(3)
        body.motion.set_mode("searching")
        time.sleep(0.5)
        seen = noticer.watch_once()
        body.motion.set_mode("idle")
        got = seen["kind"] if seen else "nothing"
        clips.append({"expect": expect, "got": got, **{k: v for k, v in (noticer.last or {}).items() if k != "top"},
                      "top": (noticer.last or {}).get("top", [])[:1]})
        print(f"clip {i + 1}: expected {expect}, got {got}; {clips[-1]}", flush=True)
        time.sleep(1.0)
    body.look(0, 0)
    summary = {"clips": len(clips), "person": args.person,
               "asked_v_jepa": sum("put" in c for c in clips),
               "false_alarms": sum(c["got"] != "nothing" and c["expect"] == "nothing" for c in clips),
               "right": sum(c["got"] == c["expect"] for c in clips),
               "put_scores": sorted(c["put"] for c in clips if "put" in c)}
    print(json.dumps(summary, indent=1))
    path = Path(args.out) / f"notice-{'person' if args.person else 'empty'}-{time.strftime('%Y%m%d-%H%M')}.json"
    path.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "clips": clips}, indent=1))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
