"""What Andy costs to keep at home, from its own GPU log: each card's power at rest and between turns, a day's
kilowatt-hours, and their price.

Since October 31 a logger has written each GPU's power, state, load and memory once a second (gpu-watch,
~/.local/state/gpu-watch/<date>.csv: numbers only). This reads the hours Andy ran (its models loaded on both cards) and
says what the two cards drew, what a day of that comes to, and its price at the U.S. average; and what a card draws
resting with its models loaded (its lowest power state, P8, logged whenever nothing had asked it anything for a while),
so what the work between turns costs above that. The cards only: the processor's own meter needs root, and the rest
of the computer (and the robot) a meter at the wall.

    uv run python scripts/energy.py                                  # every hour logged with Andy running
    uv run python scripts/energy.py --since "2026-11-02 00:00" --until "2026-11-02 05:30" --label night
"""
import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path.home() / ".local" / "state" / "gpu-watch"
# U.S. residential average, August 2026: EIA Electric Power Monthly, Table 5.6.A (published October 2026)
CENTS_PER_KWH = 18.16
PRICE_SOURCE = "EIA Electric Power Monthly, Table 5.6.A: U.S. residential average, August 2026, 18.16 cents per kWh"
DAYS_PER_MONTH = 30.4
LOADED_MIB = 15000  # a card with Andy's models on it holds more than this (GPU 0 22 GB, GPU 1 19 to 22 GB)
RESTING = "P8"


def rows(paths, since: datetime | None = None, until: datetime | None = None):
    """(time, gpu, state, watts, load %, memory MiB) for each logged second, in order."""
    for path in paths:
        with open(path) as f:
            reader = csv.reader(f)
            head = [h.strip() for h in next(reader)]
            i = {name: head.index(name) for name in ("timestamp", "index", "pstate", "power.draw", "utilization.gpu",
                                                      "memory.used")}
            for row in reader:
                try:
                    t = datetime.strptime(row[i["timestamp"]].strip(), "%Y/%m/%d %H:%M:%S.%f")
                    if (since and t < since) or (until and t >= until):
                        continue
                    yield (t, int(row[i["index"]]), row[i["pstate"]].strip(), float(row[i["power.draw"]]),
                           float(row[i["utilization.gpu"]]), float(row[i["memory.used"]]))
                except (ValueError, IndexError):
                    continue  # a line cut short when the logger stopped


def seconds(rows_) -> list[dict]:
    """One entry per logged second with both cards, kept only when Andy was running (both cards hold its models)."""
    pending, out = {}, []
    for t, gpu, state, watts, load, mib in rows_:
        pending[gpu] = (t, state, watts, load, mib)
        if len(pending) == 2:
            (t0, *a), (t1, *b) = pending[0], pending[1]
            if abs((t1 - t0).total_seconds()) < 0.5 and a[3] > LOADED_MIB and b[3] > LOADED_MIB:
                out.append({"t": t0, 0: tuple(a), 1: tuple(b)})
            pending = {}
    return out


def median(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def cost(watts: float) -> dict:
    kwh = watts * 24 / 1000
    return {"watts": round(watts, 1), "kWh a day": round(kwh, 2),
            "dollars a month": round(kwh * DAYS_PER_MONTH * CENTS_PER_KWH / 100, 2)}


def summary(secs: list[dict], resting_w: dict | None = None) -> dict:
    """What the cards drew over these seconds, and what they'd draw resting whenever nothing was asked of them.
    resting_w: each card's resting power when it's known from elsewhere (a window too busy to have rested)."""
    if not secs:
        raise SystemExit("no logged second with Andy running in that window")
    cards = {}
    for g in (0, 1):
        watts = [s[g][1] for s in secs]
        rest = [s[g][1] for s in secs if s[g][0] == RESTING]
        cards[f"GPU {g}"] = {"average W": round(sum(watts) / len(watts), 1),
                             "share of time resting": round(len(rest) / len(watts), 3),
                             "resting W (median)": round(median(rest), 1) if rest else None,
                             "load % (average)": round(sum(s[g][2] for s in secs) / len(secs), 1)}
    both = sum(c["average W"] for c in cards.values())
    resting = {g: cards[f"GPU {g}"]["resting W (median)"] or (resting_w or {}).get(g) for g in (0, 1)}
    out = {"hours": round(len(secs) / 3600, 1), "from": f"{secs[0]['t']:%Y-%m-%d %H:%M}",
           "to": f"{secs[-1]['t']:%Y-%m-%d %H:%M}", "cards": cards, "both cards": cost(both)}
    if all(resting.values()):
        out["both cards resting"] = cost(sum(resting.values()))
    return out


def logs(since: datetime | None, until: datetime | None) -> list[Path]:
    paths = sorted(LOG.glob("*.csv"))
    keep = []
    for p in paths:
        day = datetime.strptime(p.stem, "%Y-%m-%d")
        if (since and day.date() < since.date()) or (until and day.date() > until.date()):
            continue
        keep.append(p)
    return keep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="'2026-11-02 00:00'")
    ap.add_argument("--until")
    ap.add_argument("--label", default="all", help="a name for this window in the saved result")
    ap.add_argument("--save", action="store_true", help="save evals/results/energy-<date>.json (all, night, day)")
    args = ap.parse_args()
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M") if s else None  # noqa: E731
    since, until = parse(args.since), parse(args.until)
    whole = seconds(rows(logs(since, until), since, until))
    resting = {g: summary(whole)["cards"][f"GPU {g}"]["resting W (median)"] for g in (0, 1)}
    windows = {args.label: (since, until)}
    if args.save:
        windows = {"all": (since, until), "night (no turns)": (datetime(2026, 11, 2, 0, 0), datetime(2026, 11, 2, 5, 30))}
    result = {}
    for label, (a, b) in windows.items():
        secs = [s for s in whole if (a is None or s["t"] >= a) and (b is None or s["t"] < b)]
        result[label] = summary(secs, resting)
        r = result[label]
        print(f"{label}: {r['hours']} h with Andy running ({r['from']} to {r['to']})")
        for name, c in r["cards"].items():
            print(f"  {name}: {c['average W']} W on average, resting {c['share of time resting']:.0%} of the time "
                  f"(resting: {c['resting W (median)']} W), load {c['load % (average)']}%")
        both = r["both cards"]
        print(f"  both cards: {both['watts']} W = {both['kWh a day']} kWh a day = ${both['dollars a month']} a month")
        if "both cards resting" in r:
            rest = r["both cards resting"]
            print(f"  resting whenever nothing is asked: {rest['watts']} W = {rest['kWh a day']} kWh a day = "
                  f"${rest['dollars a month']} a month")
    print(f"price: {PRICE_SOURCE}")
    if args.save:
        out = ROOT / "evals" / "results" / f"energy-{time.strftime('%Y%m%d-%H%M')}.json"
        out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": __doc__.strip().splitlines()[0],
                                   "price": PRICE_SOURCE, "cents per kWh": CENTS_PER_KWH,
                                   "not measured": "the processor (its meter needs root), the rest of the computer and "
                                   "the robot: a meter at the wall would add them", "summary": result}, indent=1))
        print(f"saved {out}")


if __name__ == "__main__":
    main()
