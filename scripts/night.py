"""A night with Andy resting, against the night before it rested: the GPUs' power and price (scripts/energy.py), and
whether it still heard its own breathing (evals/ego_noise.py). One command for the morning after.

Andy rests after ten minutes with no turn (companion/rest.py, from November 2 at 17:49). The night of November 2, before
it, is the baseline: midnight to 5:30, GPU 1 at 135.3 W and 1,043 sounds an hour keeping the breath's time. This reads
the same hours of a night after it, from the same logs (numbers only: the GPU log and the journal's times), and saves
the breathing check's result (evals/results/ego-noise-<date>.json).

    uv run python scripts/night.py                    # last night, midnight to 5:30
    uv run python scripts/night.py --date 2026-11-03  # a given night
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "2026-11-02"  # the night before Andy rested
FROM, TO = "00:00", "05:30"


def run(args: list[str]) -> str:
    out = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise SystemExit(out.stderr.strip()[-400:])
    return out.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=(datetime.now()).strftime("%Y-%m-%d"),
                    help="the night that ended this morning (its date), default today")
    args = ap.parse_args()
    night = args.date
    if night <= BEFORE:
        raise SystemExit(f"the night of {night} is before Andy rested; pick a later one")
    if datetime.strptime(f"{night} {TO}", "%Y-%m-%d %H:%M") > datetime.now():
        raise SystemExit(f"the night of {night} isn't over yet (it ends at {TO})")
    label = f"night {night}, resting"
    print(f"== the night before Andy rested ({BEFORE}) and {label}, {FROM} to {TO} ==")
    for day, name in ((BEFORE, f"night {BEFORE}, before"), (night, label)):
        print(f"-- {name}")
        print(run(["scripts/energy.py", "--since", f"{day} {FROM}", "--until", f"{day} {TO}", "--label", name]).strip())
    print(run(["-m", "evals.ego_noise", "--since", f"{night} {FROM}", "--until", f"{night} {TO}", "--label", label,
               "--save"]).strip())
    # printed, not saved: energy's saved result is the cost before the fix, which the README states and claims.py checks
    print(run(["scripts/energy.py", "--since", f"{(datetime.strptime(night, '%Y-%m-%d') - timedelta(days=1)):%Y-%m-%d} 17:49",
               "--until", f"{night} {TO}", "--label", "since resting began"]).strip())
    rests = subprocess.run(["journalctl", "--user", "-u", "heyandy-app", "--since", f"{night} {FROM}", "--until",
                            f"{night} {TO}", "--no-pager", "-o", "cat"], capture_output=True, text=True).stdout
    print(f"rested {rests.count('resting:')} times, woke {rests.count('awake (')} times in those hours "
          f"(the journal's own lines; never a word)")
    print(f"made {time.strftime('%Y-%m-%d %H:%M')}: put the numbers in docs/research.md section 89 and the README")


if __name__ == "__main__":
    main()
