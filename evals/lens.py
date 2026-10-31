"""The robot measures its own lens: each thing centred by the finder, then seen from many head angles.

Where a thing appears in the picture, against where the head was and where the thing really is (where the finder
centred it), gives the camera's focal length. Pollen publishes 1116 px at 1920x1080 for the Lite; this measures ours.
Only numbers are kept (pixel positions and angles); the frames go to SAM 3.1 on this computer and nowhere else.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.lens --things watch,cup,glasses
    systemctl --user start heyandy-app
"""
import argparse
import json
import math
import time
from pathlib import Path

from heyandy_meta.finder.geometry import LITE
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.depth_local import pose
from heyandy_meta.models.sam_local import LocalSam31

OFFSETS_YAW = (-40, -30, -20, -10, 0, 10, 20, 30, 40)
OFFSETS_PITCH = (-12, 0, 12)


def _rot(yaw, pitch):
    return [row[:3] for row in pose(yaw, pitch)[:3]]


def off_axis(sample) -> tuple[float, float]:
    """The thing's angle from the optical axis of the view it was seen in, and its direction around the axis."""
    w = [sum(r * c for r, c in zip(row, (0.0, 0.0, 1.0))) for row in _rot(*sample["true"])]
    v = _rot(*sample["view"])
    d = [sum(v[k][i] * w[k] for k in range(3)) for i in range(3)]  # into the view's camera axes
    return math.acos(max(-1.0, min(1.0, d[2]))), math.atan2(d[1], d[0])


def fit(samples: list[dict], cx: float = LITE.cx, cy: float = LITE.cy) -> dict:
    """The pinhole focal length that best puts each sighting where it was seen (least squares on the radius)."""
    rows = []
    for s in samples:
        theta, _ = off_axis(s)
        rows.append((math.tan(theta), math.hypot(s["px"][0] - cx, s["px"][1] - cy)))
    f = sum(t * r for t, r in rows) / sum(t * t for t, _ in rows)

    def error(focal):
        errs = []
        for s in samples:
            theta, phi = off_axis(s)
            r = focal * math.tan(theta)
            errs.append(math.hypot(cx + r * math.cos(phi) - s["px"][0], cy + r * math.sin(phi) - s["px"][1]))
        return errs

    def summary(focal):
        errs = sorted(error(focal))
        return {"rms_px": round(math.sqrt(sum(e * e for e in errs) / len(errs)), 1), "worst_px": round(errs[-1], 1),
                "rms_deg": round(math.degrees(math.atan(math.sqrt(sum(e * e for e in errs) / len(errs)) / focal)), 2)}

    return {"focal_px": round(f, 1), "fitted": summary(f), "published_1116": summary(1116.0), "samples": len(samples)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--things", default="watch,cup,glasses")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    from heyandy_meta.robot.reachy_mini import ReachyBody

    body, sam = ReachyBody(), LocalSam31()
    finder = Finder(body, sam, verify=False)
    samples = []
    for thing in args.things.split(","):
        body.look(0, 0)
        found = finder.find(thing)
        if not found:
            print(f"{thing}: not found")
            continue
        for dy in OFFSETS_YAW:
            for dp in OFFSETS_PITCH:
                body.look(found.yaw + dy, found.pitch + dp)
                frame = body.capture()
                masks = sorted(sam.find(frame, thing), key=lambda m: -(m.score or 0.0))
                if masks and (masks[0].score or 0.0) >= 0.6:
                    samples.append({"thing": thing, "true": [found.yaw, found.pitch], "view": [frame.yaw, frame.pitch],
                                    "px": [round(c, 1) for c in masks[0].center], "size": [frame.width, frame.height]})
        print(f"{thing}: centred at {found.yaw:.1f}, {found.pitch:.1f}; {sum(s['thing'] == thing for s in samples)} sightings")
    body.look(0, 0)
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), **fit(samples), "sightings": samples}
    print(json.dumps({k: v for k, v in result.items() if k != "sightings"}, indent=1))
    out = Path(args.out) / f"lens-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
