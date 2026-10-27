"""The physical scorecard: the real robot, a real room, and a person who checks each answer.

For each trial the operator puts a thing somewhere (or hides it, for an "absent" trial), presses Enter, and the robot
searches with local SAM 3.1 and Glimmer's picture check. The operator then says whether Andy is pointing at it. Only
numbers are saved: where it pointed, the time, the looks, and the operator's verdict. No picture is kept.

    uv run python -m evals.physical --things cup,keys,glasses --places 5
    uv run python -m evals.physical --policy glimmer      # the operator also types the hint they'd say
"""
import argparse
import json
import time
from pathlib import Path

from heyandy_meta.agent.loop import plan_search
from heyandy_meta.agent.tools import SearchTools
from heyandy_meta.finder.judge import GlimmerJudge
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.sam_local import LocalSam31
from heyandy_meta.robot.reachy_mini import ReachyBody


def ask(prompt: str, choices: str) -> str:
    while True:
        a = input(f"{prompt} [{'/'.join(choices)}] ").strip().lower()[:1]
        if a in choices:
            return a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--things", default="cup,keys,glasses")
    ap.add_argument("--places", type=int, default=5)
    ap.add_argument("--absent-every", type=int, default=4, help="every Nth trial, hide the thing")
    ap.add_argument("--policy", choices=["fixed", "glimmer"], default="fixed")
    ap.add_argument("--light", default="day", help="a note on the lighting, saved with the results")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    body, judge = ReachyBody(), GlimmerJudge()
    finder = Finder(body, LocalSam31(), check=judge.real)
    glimmer = None
    if args.policy == "glimmer":
        from openai import OpenAI

        glimmer = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="local")
    trials, n = [], 0
    try:
        for thing in args.things.split(","):
            for place in range(1, args.places + 1):
                n += 1
                absent = args.absent_every and n % args.absent_every == 0
                input(f"\n#{n}: {'HIDE the ' + thing + ' (out of sight)' if absent else f'Put the {thing} at place {place}'}"
                      ", step back, then press Enter ")
                hint = input("  What would you say? (Enter for a plain request) ").strip() if glimmer else ""
                body.look(0.0, 10.0)
                start = time.monotonic()
                if glimmer:
                    tools = SearchTools(finder, judge=judge)
                    plan_search(glimmer, hint or f"where is the {thing}", tools, model="muse-glimmer-30B", paid=False)
                    found = tools.pointed
                else:
                    found = finder.find(thing)
                seconds = round(time.monotonic() - start, 1)
                if found is None:
                    verdict = "correct" if absent else "missed"
                    print(f"  Andy: not found ({seconds}s) -> {verdict}")
                else:
                    a = ask(f"  Andy points at yaw {found.yaw:+.0f}, pitch {found.pitch:+.0f} ({seconds}s). "
                            "At the thing (y), near it but off (n), or at something else (o)?", "yno")
                    verdict = {"y": "correct", "n": "off", "o": "false_find"}[a]
                    if absent:
                        verdict = "false_find"
                trials.append({"n": n, "thing": thing, "place": None if absent else place, "absent": bool(absent),
                               "hint": hint, "verdict": verdict, "seconds": seconds, "looks": finder.looks,
                               "pointed": None if found is None else [round(found.yaw, 1), round(found.pitch, 1)]})
    except (KeyboardInterrupt, EOFError):
        print("\nstopped; saving what was done")
    finally:
        body.look(0.0, 0.0)
    done = [t for t in trials if not t["absent"]]
    summary = {"trials": len(trials), "present": len(done),
               "correct": sum(t["verdict"] == "correct" for t in done),
               "absent_correct": sum(t["verdict"] == "correct" for t in trials if t["absent"]),
               "false_finds": sum(t["verdict"] == "false_find" for t in trials),
               "seconds_median": sorted(t["seconds"] for t in trials)[len(trials) // 2] if trials else None}
    path = Path(args.out) / f"physical-{args.policy}-{time.strftime('%Y%m%d-%H%M')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"policy": args.policy, "light": args.light, "summary": summary, "trials": trials}, indent=1))
    print(json.dumps(summary, indent=1), "\nsaved", path)
    body.robot.__exit__(None, None, None)


if __name__ == "__main__":
    main()
