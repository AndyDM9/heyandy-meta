"""Andy's eyes, live: the public demo's "Sweep the room" (screen/eyes.html), with a camera that's a video.

Chromium's fake camera plays a sweep over our museum photos (The Met, CC0; screen/eyes/), 10 frames a second, 640 by
360: first the four cups without ours, then the four with it, two ways of sweeping (the whole width, top to bottom
and back; and closer, row by row). Our cup is shown once ("No photo to hand? Use our cup"), then the sweep runs in the
page, on the CPU as most visitors' will, until it says "There's your cup" or the time is up. Also each sweep with only
the four others, which must never end in "found". Kept: when it found it, each frame's numbers, the closer looks.

    uv run --with playwright python -m evals.eyes_live           # about 6 minutes; DINOv2 downloads once (24 MB)
"""
import functools
import http.server
import io
import json
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "heyandy_meta" / "screen"
W, H, FPS, EACH_S = 640, 360, 10, 8.0


def windows(img: Image.Image, how: str, n: int):
    """n crops of a picture, as a camera sweeping over it would see them."""
    if how == "wide":  # the whole width, top to bottom and back up
        cw, ch = img.width, round(img.width * H / W)
        for i in range(n):
            t = i / max(1, n - 1)
            y = round((img.height - ch) * (1 - abs(2 * t - 1)))
            yield (0, y, cw, y + ch)
    else:  # closer: 60% of the width, along the top row, then back along the bottom row
        cw = round(img.width * 0.6); ch = round(cw * H / W)
        for i in range(n):
            t = i / max(1, n - 1)
            x = round((img.width - cw) * (2 * t if t < 0.5 else 2 - 2 * t))
            y = 0 if t < 0.5 else img.height - ch
            yield (x, y, x + cw, y + ch)


def video(out: Path, pictures: list[Path], how: str) -> Path:
    """A Y4M file (it carries its frame rate, which Chromium keeps) of a sweep over each picture in turn."""
    mjpeg = out.with_suffix(".mjpeg")
    with open(mjpeg, "wb") as f:
        for path in pictures:
            img = Image.open(path).convert("RGB")
            for box in windows(img, how, int(EACH_S * FPS)):
                b = io.BytesIO()
                img.crop(box).resize((W, H), Image.LANCZOS).save(b, "JPEG", quality=88)
                f.write(b.getvalue())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "mjpeg", "-framerate", str(FPS), "-i", str(mjpeg),
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    mjpeg.unlink()
    return out


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def sweep(p, profile: Path, site: str, camera: Path, limit_s: float) -> dict:
    ctx = p.chromium.launch_persistent_context(
        str(profile), headless=True, viewport={"width": 1280, "height": 900}, permissions=["camera"],
        args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
              f"--use-file-for-fake-video-capture={camera}"])
    try:
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{site}/eyes.html")
        page.wait_for_function("window.EYES_READY === true")
        page.click("#ours1")
        page.wait_for_selector("#known:not([hidden])", timeout=300000)
        device = "gpu" if "on its GPU" in page.text_content("#live") else "cpu"
        t0 = time.monotonic()
        page.click("#sweep")
        found_s = None
        while time.monotonic() - t0 < limit_s:
            if page.query_selector("#stage2 .spot") and page.text_content("#said").startswith("There's your"):
                found_s = round(time.monotonic() - t0, 1)
                break
            time.sleep(0.2)
        log = page.evaluate("() => window.sweepLog")
        return {"found_s": found_s, "said": page.text_content("#said"), "why": page.text_content("#why"),
                "device": device, "frames": [x for x in log if "whole" in x], "closer": [x for x in log if "closer" in x],
                "errors": errors}
    finally:
        ctx.close()


def main() -> None:
    from playwright.sync_api import sync_playwright

    others, ours = SCREEN / "eyes" / "cups-without.webp", SCREEN / "eyes" / "cups.webp"
    handler = functools.partial(Quiet, directory=str(SCREEN))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    runs = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        tmp = Path(tmp)
        for how in ("wide", "closer"):
            for kind, pictures, limit in (("with", [others, ours], 60.0), ("without", [others, others], 45.0)):
                cam = video(tmp / f"{how}-{kind}.y4m", pictures, how)
                r = sweep(p, tmp / "profile", site, cam, limit)  # one profile: DINOv2 downloads once
                r.update(sweep=how, cup=kind)
                runs.append(r)
                fr = r["frames"]
                print(f"{how:6} {kind:7} found at {r['found_s']} s | {len(fr)} frames, "
                      f"most alike {max((x['whole'] for x in fr), default=0):.2f} | closer looks "
                      f"{[(x['closer'], x['says']) for x in r['closer']]} | {r['said']!r}", flush=True)
    server.shutdown()
    with_ = [r for r in runs if r["cup"] == "with"]
    without = [r for r in runs if r["cup"] == "without"]
    frames = [x for r in runs for x in r["frames"]]
    gaps = [b["at"] - a["at"] for r in runs for a, b in zip(r["frames"], r["frames"][1:])]
    summary = {
        "sweeps with our cup": len(with_), "found it": sum(r["found_s"] is not None for r in with_),
        "seconds to 'There's your cup'": [r["found_s"] for r in with_],
        "sweeps without it": len(without), "said found without it": sum(r["found_s"] is not None for r in without),
        "most alike, without it": max((x["whole"] for r in without for x in r["frames"]), default=None),
        "closer looks without it": sum(len(r["closer"]) for r in without),
        "frames": len(frames), "seconds a frame, median": round(statistics.median(gaps) / 1000, 2) if gaps else None,
        "device": runs[0]["device"] if runs else None, "script errors": sum(len(r["errors"]) for r in runs),
    }
    out = ROOT / "evals" / "results" / f"eyes-live-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary,
                               "camera": f"a video, {W}x{H}, {FPS} frames a second, {EACH_S:.0f} s a picture",
                               "photos": "The Metropolitan Museum of Art, Open Access (CC0); screen/eyes/CREDITS.txt",
                               "runs": runs}, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
