"""The unattended run: the real robot searches, again and again, for things that are always in the room.

Nobody checks what Andy pointed at, so this measures the robot, not the finding: how often a search ends in a point,
how long it takes, how many looks, how far off the middle the point landed (Andy's own check after pointing), and
whether anything breaks over many runs (a frame that doesn't come, a head that doesn't settle). The physical
scorecard (evals/physical.py), with a person saying "at it" or not, is what measures the finding.

Pictures go only to SAM 3.1 and Glimmer on this computer and are never kept; only the numbers are saved. Andy's own
service holds the robot, so stop it first:

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.unattended --things keyboard,monitor,chair --rounds 5
    systemctl --user start heyandy-app
"""
import argparse
import json
import random
import time
from pathlib import Path

from heyandy_meta.finder.judge import GlimmerJudge
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.sam_local import LocalSam31
from heyandy_meta.robot.reachy_mini import ReachyBody


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def summarise(trials: list[dict]) -> dict:
    ok = [t for t in trials if t.get("error") is None]
    found = [t for t in ok if t["pointed"]]
    return {"trials": len(trials), "errors": len(trials) - len(ok), "pointed": len(found),
            "seconds_median": median(t["seconds"] for t in found),
            "looks_median": median(t["looks"] for t in found),
            "aim_deg_median": median(t["aim_deg"] for t in found),
            "aim_deg_worst": max((t["aim_deg"] for t in found if t["aim_deg"] is not None), default=None),
            "reaimed": sum(t["reaimed"] for t in found),
            "aim_not_seen": sum(t["aim_deg"] is None for t in found)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--things", default="keyboard,monitor,chair")
    ap.add_argument("--rounds", type=int, default=5, help="searches for each thing")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-check", action="store_true", help="skip Glimmer's picture check (faster)")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    body = ReachyBody()
    judge = None if args.no_check else GlimmerJudge()
    finder = Finder(body, LocalSam31(), check=judge.real if judge else None)
    trials = []
    try:
        for r in range(args.rounds):
            for thing in args.things.split(","):
                start_from = (rnd.uniform(-50, 50), rnd.uniform(-5, 20))  # a different starting pose each time
                body.look(*start_from)
                t0, row = time.monotonic(), {"round": r + 1, "thing": thing, "from": [round(v, 1) for v in start_from]}
                try:
                    found = finder.find(thing)
                    row.update(pointed=found is not None, seconds=round(time.monotonic() - t0, 1), looks=finder.looks,
                               aim_deg=found.aim_deg if found else None, reaimed=bool(found and found.reaimed),
                               why=finder.why, error=None)
                except Exception as e:  # noqa: BLE001 - a failure is a result here, and the run goes on
                    row.update(pointed=False, seconds=round(time.monotonic() - t0, 1), looks=finder.looks,
                               aim_deg=None, reaimed=False, why="", error=f"{type(e).__name__}: {e}"[:160])
                trials.append(row)
                print(json.dumps(row), flush=True)
    except KeyboardInterrupt:
        print("stopped; saving what was done")
    finally:
        body.look(0.0, 0.0)
    summary = summarise(trials)
    path = Path(args.out) / f"unattended-{time.strftime('%Y%m%d-%H%M')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"things": args.things, "check": not args.no_check, "summary": summary,
                                "note": "nobody checked what was pointed at: this measures the robot, not the finding",
                                "trials": trials}, indent=1))
    print(json.dumps(summary, indent=1), "\nsaved", path)
    body.robot.__exit__(None, None, None)


if __name__ == "__main__":
    main()
