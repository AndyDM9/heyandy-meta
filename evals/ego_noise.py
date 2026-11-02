"""Does Andy hear its own breathing? From the journal's times alone: never a sound, never a word.

Between moves Andy breathes: the head rises and falls and the antennas sway, 0.22 times a second (robot/motion.py),
and the motors turn back twice in each breath. Each sound the microphones cut out as speech and Andy let go (not for
it) leaves one journal line with its time, its length and the room's level, nothing else. If those sounds were people,
their times would fall anywhere in the breath; if they're Andy's own motors, they keep time with it. The Rayleigh test
says which: the sounds' phases in the breath (and at twice its rate, once for each turning back), how far from even
they are (the resultant, 0 to 1), and z = n R squared (above 6.9, less than a one in a thousand chance of being even).
And a control: the same test at every other rate from 0.15 to 0.30 a second (a ten-thousandth apart): sounds that keep
the breath's own time stand out at it alone.

    uv run python -m evals.ego_noise --since "2026-11-02 00:00" --until "2026-11-02 05:30" --label night
    uv run python -m evals.ego_noise --save      # the night and the day of November 2, and since the fix
"""
import argparse
import json
import math
import re
import subprocess
import time
from pathlib import Path

from heyandy_meta.robot.motion import Motion

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^(\d+\.\d+) .*\(heard (\d+\.\d)s of speech, room level (\d+\.\d+); not for Andy\)")
BINS = 12


def sounds(journal: str) -> list[tuple[float, float, float]]:
    """(when, seconds long, the room's level) of each sound Andy let go, from `journalctl -o short-unix` lines."""
    out = []
    for line in journal.splitlines():
        m = LINE.match(line)
        if m:
            out.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    return out


def rayleigh(times: list[float], hz: float, harmonic: int = 1) -> tuple[float, float]:
    """(resultant, z) of the times' phases at `harmonic` times `hz`: 0 and 0 for times spread evenly."""
    if not times:
        return 0.0, 0.0
    w = 2 * math.pi * hz * harmonic
    c, s = sum(math.cos(w * t) for t in times), sum(math.sin(w * t) for t in times)
    r = math.hypot(c, s) / len(times)
    return r, len(times) * r * r


def control(times: list[float], hz: float, lo: float = 0.15, hi: float = 0.30, step: float = 0.0001) -> dict:
    """The largest z at any other rate (twice a breath, as the motors turn back), away from the breath's own."""
    best = (0.0, None)
    for i in range(int(round((hi - lo) / step)) + 1):
        f = lo + i * step
        if abs(f - hz) > step / 2:
            best = max(best, (rayleigh(times, f, 2)[1], round(f, 4)), key=lambda x: x[0])
    return {"largest z at any other rate": round(best[0], 1), "at": best[1]}


def phases(times: list[float], hz: float) -> list[int]:
    period = 1 / hz
    counts = [0] * BINS
    for t in times:
        counts[min(BINS - 1, int((t % period) / period * BINS))] += 1
    return counts


def judge(found: list[tuple[float, float, float]], hz: float, start: float, end: float) -> dict:
    times = [t for t, _, _ in found]
    hours = max((end - start) / 3600, 1e-9)
    once, twice = rayleigh(times, hz, 1), rayleigh(times, hz, 2)
    ordered = sorted(d for _, d, _ in found)
    levels = sorted(level for _, _, level in found)
    return {"sounds let go": len(found), "an hour": round(len(found) / hours),
            "with the breath (once a breath)": {"resultant": round(once[0], 3), "z": round(once[1], 1)},
            "with the breath (twice a breath)": {"resultant": round(twice[0], 3), "z": round(twice[1], 1)},
            "control": (other := control(times, hz) if times else None),
            # standing out: past chance (6.9) and past every other rate's z, so it's the breath's own time
            "keeps time with the breath": bool(other) and max(once[1], twice[1]) > max(6.9, other["largest z at any other rate"]),
            "phase in the breath (12 parts)": (bins := phases(times, hz)),
            # how many kept the breath's time, roughly: what's above the four quietest parts' level, as if that were even
            "share above even (estimate)": round(max(0.0, 1 - BINS * sum(sorted(bins)[:4]) / 4 / len(times)), 2)
            if times else None,
            "median seconds long": ordered[len(ordered) // 2] if ordered else None,
            "median room level": levels[len(levels) // 2] if levels else None}


def journal(since: str, until: str | None) -> str:
    cmd = ["journalctl", "--user", "-u", "heyandy-app", "--since", since, "--no-pager", "-o", "short-unix"]
    if until:
        cmd += ["--until", until]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"journalctl: {out.stderr.strip()[:200]}")
    return out.stdout


def window(since: str, until: str | None, hz: float) -> dict:
    found = sounds(journal(since, until))
    start = time.mktime(time.strptime(since, "%Y-%m-%d %H:%M"))
    end = time.mktime(time.strptime(until, "%Y-%m-%d %H:%M")) if until else time.time()
    return {"from": since, "to": until or time.strftime("%Y-%m-%d %H:%M"), **judge(found, hz, start, end)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-11-02 00:00")
    ap.add_argument("--until")
    ap.add_argument("--label", default="window")
    ap.add_argument("--save", action="store_true", help="the night and the day of November 2 (and --since/--until "
                    "as 'after', when given), saved to evals/results/ego-noise-<date>.json")
    args = ap.parse_args()
    hz = Motion().breathe_hz
    windows = {args.label: (args.since, args.until)}
    if args.save:
        windows = {"night, no turns (Nov 2)": ("2026-11-02 00:00", "2026-11-02 05:30"),
                   "day, people about (Nov 2)": ("2026-11-02 09:00", "2026-11-02 17:40")}
        if args.until or args.since != "2026-11-02 00:00":
            windows[args.label] = (args.since, args.until)
    result = {}
    for label, (a, b) in windows.items():
        r = result[label] = window(a, b, hz)
        twice = r["with the breath (twice a breath)"]
        print(f"{label}: {r['sounds let go']} sounds let go ({r['an hour']} an hour); with the breath twice a breath: "
              f"resultant {twice['resultant']}, z {twice['z']}: "
              f"{'keeps time with the breath' if r['keeps time with the breath'] else 'no sign of the breath'}"
              + (f" (any other rate: z {r['control']['largest z at any other rate']} at most)" if r["control"] else ""))
    if args.save:
        out = ROOT / "evals" / "results" / f"ego-noise-{time.strftime('%Y%m%d-%H%M')}.json"
        out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": __doc__.strip().splitlines()[0],
                                   "breaths a second": hz, "summary": result}, indent=1))
        print(f"saved {out}")


if __name__ == "__main__":
    main()
