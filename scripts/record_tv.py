"""Record the TV page to a video, for the demo film: what Andy's screen showed, beside the footage of the robot.

    uv run --with playwright playwright install ffmpeg      # once: Playwright's own ffmpeg, in the user cache
    uv run --with playwright python scripts/record_tv.py --seconds 90 --out film/tv-take1.webm --room-is-staged

For filming in the staged room only: the recording keeps whatever the TV shows (the found picture, captions). It
drives a browser already open for automation (Chrome with --remote-debugging-port, default 9333), or starts a
headless one if none is there. Nothing is uploaded. Beside the video, <out>.json says when the recording started (this
computer's clock), so make_film.py sync can line it up with a take's clap ("take two", in filming mode).
"""
import argparse
import json
import shutil
import urllib.request
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765/")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default="film/tv.webm")
    ap.add_argument("--cdp", default="http://127.0.0.1:9333", help="an open Chrome's debugging address ('' for headless)")
    ap.add_argument("--room-is-staged", action="store_true",
                    help="the room has no people or anything personal in view (or this is the sample demo)")
    args = ap.parse_args()
    # The TV can show what the camera saw: record it only in a staged room (Andy started with --staged-scene says so).
    with urllib.request.urlopen(args.url.rstrip("/") + "/state.json", timeout=5) as r:
        staged = json.load(r).get("staged")
    if not (staged or args.room_is_staged):
        raise SystemExit("Not recording: Andy isn't in a staged scene. Film only in a staged room, then pass "
                         "--room-is-staged (or start Andy with --staged-scene).")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / ".recording"
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(args.cdp) if args.cdp else pw.chromium.launch()
        except Exception:  # noqa: BLE001 - no open Chrome: a headless one (needs `playwright install chromium`)
            browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  record_video_dir=str(tmp), record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        started = time.time()  # the recording's first frame, near enough (it starts with the page)
        page.goto(args.url)
        print(f"recording {args.url} for {args.seconds:.0f} s ...")
        start = time.monotonic()
        while time.monotonic() - start < args.seconds:
            page.wait_for_timeout(500)
        video = page.video.path()
        ctx.close()
        browser.close()
    shutil.move(video, out)
    shutil.rmtree(tmp, ignore_errors=True)
    out.with_suffix(".json").write_text(json.dumps({"started": round(started, 3), "url": args.url}))
    print("saved", out)


if __name__ == "__main__":
    main()
