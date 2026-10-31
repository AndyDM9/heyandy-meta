"""The room in 3D, measured: do the five looks agree on where each thing is, and from one scan to the next?

Each scan is the robot's own "show me the room": five looks, SAM 3.1 for the things in each, MapAnything joining them
(local/depth_server.py /scan). For every thing seen in more than one look, how far apart its directions and distances
came out within a scan; and where each merged thing landed, scan to scan. Only numbers are kept.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.room --things keys,glasses,cup,watch,keyboard --scans 3
    systemctl --user start heyandy-app
"""
import argparse
import json
import math
import time
from pathlib import Path

from heyandy_meta.app import ROOM_PITCH, ROOM_VIEWS, room_things
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.depth_local import LocalDepth
from heyandy_meta.models.sam_local import LocalSam31


def direction(point) -> tuple[float, float]:
    x, y, z = point
    return round(math.degrees(math.atan2(-x, z)), 1), round(math.degrees(math.atan2(y, math.hypot(x, z))), 1)


def spread(seen: list[dict], within_m: float = 0.3) -> dict:
    """For each label, the sightings within 30 cm of its strongest one: their spread in direction and distance."""
    out = {}
    for label in sorted({t["label"] for t in seen}):
        mine = sorted((t for t in seen if t["label"] == label), key=lambda t: -(t.get("score") or 0.0))
        near = [t for t in mine if math.dist(t["point"], mine[0]["point"]) <= within_m]
        if len(near) < 2:
            continue
        yaws = [direction(t["point"])[0] for t in near]
        metres = [t["metres"] for t in near]
        out[label] = {"looks": len(near), "yaw_spread_deg": round(max(yaws) - min(yaws), 1),
                      "metres_spread": round(max(metres) - min(metres), 2), "yaws": yaws, "metres": metres}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--things", default="keys,glasses,cup,watch,keyboard")
    ap.add_argument("--scans", type=int, default=3)
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    from heyandy_meta.robot.reachy_mini import ReachyBody

    body, sam, depth = ReachyBody(), LocalSam31(), LocalDepth()
    finder = Finder(body, sam)
    names = args.things.split(",")[:8]
    scans = []
    for n in range(args.scans):
        looks, start = [], time.monotonic()
        for yaw in ROOM_VIEWS:
            body.look(yaw, ROOM_PITCH, precise=False)
            frame = body.capture()
            masks = [m for ms in sam.find_many(frame, names).values() for m in ms if (m.score or 0.0) >= 0.6]
            looks.append((frame, finder._cam(frame), masks))
        out = depth.scan(looks, timeout=180)
        looks.clear()
        merged = room_things(out["things"])
        scans.append({"seconds": round(time.monotonic() - start, 1), "scan_s": out["seconds"], "points": out["n"],
                      "within": spread(out["things"]),
                      "things": [{k: t[k] for k in ("label", "yaw", "pitch", "metres", "views")} for t in merged]})
        print(f"scan {n + 1}: {scans[-1]['seconds']} s ({out['seconds']} s MapAnything, {out['n']} points); "
              + "; ".join(f"{t['label']} {t['yaw']} deg {t['metres']} m x{t['views']}" for t in merged))
    body.look(0, 0)
    across = {}
    for label in sorted({t["label"] for s in scans for t in s["things"]}):
        firsts = [next(t for t in s["things"] if t["label"] == label) for s in scans
                  if any(t["label"] == label for t in s["things"])]
        across[label] = {"scans": len(firsts), "yaw_spread_deg": round(max(t["yaw"] for t in firsts) - min(t["yaw"] for t in firsts), 1),
                         "metres_spread": round(max(t["metres"] for t in firsts) - min(t["metres"] for t in firsts), 2)}
    within = [v["yaw_spread_deg"] for s in scans for v in s["within"].values()]
    summary = {"scans": len(scans), "within_scan_yaw_spread_median": sorted(within)[len(within) // 2] if within else None,
               "within_scan_yaw_spread_worst": max(within, default=None), "across_scans": across}
    print(json.dumps(summary, indent=1))
    path = Path(args.out) / f"room-{time.strftime('%Y%m%d-%H%M')}.json"
    path.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "scans": scans}, indent=1))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
