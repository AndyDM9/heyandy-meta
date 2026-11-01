"""The video's own cards, rendered here: the title, the numbers and the models, and the end, as 1080p MP4s.

The robot's takes are filmed; these three pieces are made, in HeyAndy's look (the TV's fonts and colours), so filming
day is only the robot. Every figure on the numbers card is read from evals/results when it's rendered and checked
there (a figure the files don't support stops the render), so the film can't say more than the evidence. Each frame
is drawn on its own (every animation set to that instant, then a screenshot), not screen-recorded: sharp, and the
same every time. Nothing is uploaded; the pieces go in film/ (git-ignored).

    uv run python scripts/film_cards.py                       # -> film/card-title.mp4, card-numbers.mp4, card-end.mp4
    uv run python scripts/film_cards.py --only numbers --check  # the figures and their files, without rendering
    uv run python scripts/film_cards.py --line "Before this week: ..."   # the title card's first line, the founder's words

The demo script (docs/demo-script.md) places them: the title at 0:00, the numbers at 2:16, the end at 2:44.
"""
import argparse
import glob
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
FFMPEG = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FPS = 30
LINE = ("Before this week: a Reachy Mini, and our own earlier object-finding prototype. "
        "Everything you'll see was built this week, on Meta's models.")
DEMO = "huggingface.co/spaces/heyandy-ai/andy"
REPO = "github.com/AndyDM9/heyandy-meta"


def _load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def figures() -> list[dict]:
    """The numbers card: each figure with the line under it and the file it comes from, computed from the files."""
    runs = sorted(glob.glob(str(RESULTS / "unattended-*.json")))
    after_fix = [json.loads(Path(f).read_text())["summary"] for f in runs if Path(f).name > "unattended-20261030-1714.json"]
    trials, pointed = sum(s["trials"] for s in after_fix), sum(s["pointed"] for s in after_fix)
    final = _load("unattended-20261031-1106.json")["summary"]
    privacy = _load("privacy-audit.json")["summary"]
    spark, glimmer = _load("agent-spark.json")["summary"], _load("agent-glimmer.json")["summary"]
    room = _load("room-20261031-1129.json")["summary"]["across_scans"]
    lost = _load("lost-20261031-1653.json")
    langs, spanish = _load("languages-20261101-1548.json")["summary"], _load("spanish-written.json")["summary"]
    sound = _load("sound-20261031-1856.json")
    out = [
        {"big": f"{pointed} of {trials}", "line": "unattended searches on the robot ended in a point",
         "from": "evals/results/unattended-*", "ok": trials >= 100 and pointed == trials},
        {"big": f"{final['aim_deg_median']}°", "line": "median off the middle, checked by its own camera after each point",
         "from": "unattended-20261031-1106", "ok": final["pointed"] == final["trials"]},
        {"big": f"{privacy['camera_pictures_to_cloud']} of {privacy['camera_pictures_taken']}",
         "line": f"camera pictures reached the cloud, in a day of {privacy['turns']} requests", "from": "privacy-audit",
         "ok": privacy["camera_pictures_to_cloud"] == 0},
        {"big": f"{langs['written right'] + spanish['right']} of {langs['requests'] + spanish['requests']}",
         "line": f"everyday requests, written in {langs['languages'] + 1} languages besides English, reached the right ability",
         "from": "languages-20261101-1548, spanish-written",
         "ok": langs["written right"] == langs["requests"] and spanish["right"] == spanish["requests"]},
        {"big": f"{glimmer['right']} of {glimmer['requests']}",
         "line": "requests with several steps, done offline (Muse Glimmer); "
                 f"{spark['right']} of {spark['requests']} with Muse Spark", "from": "agent-glimmer, agent-spark",
         "ok": glimmer["right"] == glimmer["requests"] and spark["right"] == spark["requests"]},
        {"big": f"{max(v['yaw_spread_deg'] for v in room.values()):.0f}° · {max(v['metres_spread'] for v in room.values()) * 100:.0f} cm",
         "line": "the room in 3D, scan to scan (MapAnything)", "from": "room-20261031-1129", "ok": True},
        {"big": f"{lost['pointed_at']['aim_deg']}°",
         "line": "a lost watch turned up: found later, pointed at and said, unprompted", "from": "lost-20261031-1653",
         "ok": bool(lost["said"]) and lost["said"].startswith("Good news")},
        {"big": f"{sound['ringings_faced']} of {sound['of']}",
         "line": f"ringings turned to from three starts, within {max(sound['spread_deg'].values()):.0f}°; a voice never",
         "from": "sound-20261031-1856", "ok": not sound["voice_taken_for_a_ringing"]},
    ]
    bad = [f["from"] for f in out if not f["ok"]]
    if bad:
        raise SystemExit(f"these figures aren't what their files say: {', '.join(bad)}")
    return out


MODELS = [("SAM 3.1", "finds and outlines"), ("Muse Glimmer", "plans, checks, translates"),
          ("MapAnything", "how far; the room in 3D"), ("V-JEPA 2", "sees a thing put down"),
          ("DINOv2", "knows your mug"), ("Omnilingual ASR", "hears"), ("SeamlessM4T v2", "speaks"),
          ("Llama Guard 3", "a crisis check"), ("Prompt Guard 2", "spots tricks in web pages")]
CLOUD = [("Muse Spark", "the agent and the web: words, and web pages"), ("Muse Image", "drawings, from words")]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Atkinson Next"; src: url("AtkinsonHyperlegibleNext.ttf"); font-weight: 200 800; }
@font-face { font-family: "Atkinson Mono"; src: url("AtkinsonHyperlegibleMono.ttf"); font-weight: 200 800; }
* { box-sizing: border-box; margin: 0; }
html, body { width: 1920px; height: 1080px; overflow: hidden; }
body { background: radial-gradient(ellipse at 72% 18%, #1d2a24, #070a09 68%); color: #F5F3EF; font-family: "Atkinson Next", sans-serif; }
.card { position: absolute; inset: 0; padding: 110px 150px; display: flex; flex-direction: column; }
.sig { position: absolute; left: 150px; top: 110px; height: 56px; width: auto; }
.card.center { justify-content: center; } .card.center h1 { margin-top: 0; }
.in { opacity: 0; animation: in 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
@keyframes in { from { opacity: 0; transform: translateY(28px); } to { opacity: 1; transform: none; } }
.pop { opacity: 0; animation: pop 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.2) both; }
@keyframes pop { from { opacity: 0; transform: scale(0.86); } to { opacity: 1; transform: none; } }
.out { animation: out 0.6s ease-in both; } @keyframes out { to { opacity: 0; } }
em { font-style: normal; color: #ffcf5c; }
h1 { font-size: 112px; font-weight: 800; line-height: 1.0; letter-spacing: -0.03em; margin-top: 70px; }
.line { font-size: 38px; line-height: 1.35; color: rgba(245, 243, 239, 0.82); max-width: 1400px; margin-top: 44px; }
.small { position: absolute; left: 150px; bottom: 90px; font-size: 26px; color: rgba(245, 243, 239, 0.55); }
.kick { font: 700 28px "Atkinson Mono", monospace; letter-spacing: 0.16em; text-transform: uppercase; color: #ffcf5c; }
.figs { display: grid; grid-template-columns: repeat(2, 1fr); gap: 34px 80px; margin-top: 48px; }
.fig b { display: block; font: 700 92px/1 "Atkinson Mono", monospace; color: #ffcf5c; letter-spacing: -0.02em; }
.fig span { display: block; font-size: 30px; line-height: 1.3; margin-top: 10px; color: rgba(245, 243, 239, 0.9); }
.fig small { display: block; font: 500 19px "Atkinson Mono", monospace; margin-top: 6px; color: rgba(245, 243, 239, 0.45); }
h2 { font-size: 72px; font-weight: 800; letter-spacing: -0.02em; margin-top: 30px; }
.where { font: 700 24px "Atkinson Mono", monospace; letter-spacing: 0.12em; text-transform: uppercase; margin: 46px 0 18px;
         color: rgba(245, 243, 239, 0.6); }
.models { display: flex; flex-wrap: wrap; gap: 18px; }
.models div { padding: 18px 28px; border-radius: 22px; background: rgba(245, 243, 239, 0.07); border: 2px solid rgba(245, 243, 239, 0.18); }
.models.cloud div { border-color: rgba(255, 207, 92, 0.6); }
.models b { display: block; font-size: 36px; } .models span { font-size: 23px; color: rgba(245, 243, 239, 0.7); }
.go { margin-top: 60px; display: grid; gap: 22px; font-size: 44px; }
.go b { color: #ffcf5c; font-family: "Atkinson Mono", monospace; font-weight: 700; }
.face { position: absolute; right: 150px; top: 110px; width: 220px; }
.eye { transform-box: fill-box; transform-origin: center; animation: blink 4.2s infinite; }
@keyframes blink { 0%, 46%, 50%, 100% { transform: scaleY(1); } 48% { transform: scaleY(0.08); } }
</style></head><body>__BODY__
<script>
// One instant of the card: every animation paused at t ms, every counter at its value then. The renderer calls it
// once a frame, so each frame is exactly that moment, however long the screenshot takes.
const counters = [...document.querySelectorAll("[data-to]")];
window.at = t => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t; }
  for (const c of counters) {
    const start = +c.dataset.start, f = Math.min(1, Math.max(0, (t - start) / 1100)), e = 1 - Math.pow(1 - f, 3);
    c.textContent = c.dataset.to.replace(/\\d+(?:\\.\\d+)?/g, n => (n.includes(".") ? (parseFloat(n) * e).toFixed(1) : Math.round(+n * e)));
  }
};
</script></body></html>"""

FACE = ('<svg class="face in" style="animation-delay: 0.3s" viewBox="0 0 380 210"><rect x="4" y="3" width="372" height="203" '
        'rx="101.5" fill="#F5F3EF"/><ellipse class="eye" cx="102.3" cy="108.5" rx="18.9" ry="37.3" fill="#070a09"/>'
        '<ellipse class="eye" cx="279" cy="108.5" rx="18.9" ry="37.3" fill="#070a09"/></svg>')


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def title(line: str) -> tuple[str, float]:
    sig = (ROOT / "docs" / "images" / "heyandy-signature-reversed.svg").read_text().replace("<svg ", '<svg class="sig in" ', 1)
    body = (f'<div class="card center">{sig}{FACE}<h1 class="in" style="animation-delay: 0.5s">Andy finds what you\'ve lost,<br>'
            f'<em>and points at it.</em></h1><p class="line in" style="animation-delay: 1.4s">{_esc(line)}</p>'
            '<p class="small in" style="animation-delay: 2.2s">HeyAndy, Inc. · Meta\'s Global AI Developer Hackathon</p></div>')
    return body, 6.0


def numbers(figs: list[dict]) -> tuple[str, float]:
    step, first = 1.5, 0.9
    tiles = "".join(
        f'<div class="fig pop" style="animation-delay: {first + i * step:.2f}s"><b data-to="{_esc(f["big"])}" '
        f'data-start="{(first + i * step) * 1000:.0f}">{_esc(f["big"])}</b><span>{_esc(f["line"])}</span>'
        f'<small>{_esc(f["from"])}</small></div>' for i, f in enumerate(figs[:6]))
    shown = first + 6 * step + 3.0  # the figures, then a moment to read them
    on = "".join(f'<div class="pop" style="animation-delay: {shown + 1.0 + i * 0.35:.2f}s"><b>{n}</b><span>{w}</span></div>'
                 for i, (n, w) in enumerate(MODELS))
    up = "".join(f'<div class="pop" style="animation-delay: {shown + 1.3 + (len(MODELS) + i) * 0.35:.2f}s"><b>{n}</b><span>{w}</span></div>'
                 for i, (n, w) in enumerate(CLOUD))
    body = (f'<div class="card out" style="animation-delay: {shown - 0.6:.2f}s"><p class="kick in">Measured: every figure from evals/results</p>'
            f'<div class="figs">{tiles}</div></div>'
            f'<div class="card"><p class="kick in" style="animation-delay: {shown:.2f}s">Every model Andy runs is Meta\'s</p>'
            f'<h2 class="in" style="animation-delay: {shown + 0.3:.2f}s">Eleven, and the camera reaches only the ones at home.</h2>'
            f'<p class="where in" style="animation-delay: {shown + 0.8:.2f}s">On the computer beside the robot</p><div class="models">{on}</div>'
            f'<p class="where in" style="animation-delay: {shown + 1.2 + len(MODELS) * 0.35:.2f}s">In the cloud, never a camera picture</p>'
            f'<div class="models cloud">{up}</div></div>')
    return body, shown + 1.3 + (len(MODELS) + len(CLOUD)) * 0.35 + 4.5


def end() -> tuple[str, float]:
    sig = (ROOT / "docs" / "images" / "heyandy-signature-reversed.svg").read_text().replace("<svg ", '<svg class="sig in" ', 1)
    body = (f'<div class="card center">{sig}{FACE}<h1 class="in" style="animation-delay: 0.4s">Andy finds what you\'ve lost.<br>'
            f'<em>Every model it runs is Meta\'s.</em></h1><div class="go">'
            f'<p class="in" style="animation-delay: 1.4s">Ask Andy yourself: <b>{DEMO}</b></p>'
            f'<p class="in" style="animation-delay: 2.0s">How it\'s built: <b>{REPO}</b></p></div>'
            '<p class="small in" style="animation-delay: 2.8s">HeyAndy, Inc. · heyandy.ai · Andy gives no health advice.</p></div>')
    return body, 12.0


def render(body: str, seconds: float, out: Path, size=(1920, 1080)) -> None:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="andy-card-") as tmp:
        tmp = Path(tmp)
        for font in ("AtkinsonHyperlegibleNext.ttf", "AtkinsonHyperlegibleMono.ttf"):
            shutil.copy(ROOT / "heyandy_meta" / "screen" / "fonts" / font, tmp / font)
        (tmp / "card.html").write_text(PAGE.replace("__BODY__", body))
        (tmp / "frames").mkdir()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            page.goto((tmp / "card.html").as_uri())
            page.evaluate("document.fonts.ready")
            for i in range(round(seconds * FPS)):
                page.evaluate("t => window.at(t)", i * 1000 / FPS)
                page.screenshot(path=str(tmp / "frames" / f"{i:05d}.png"))
            browser.close()
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "frames" / "%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", "-movflags", "+faststart",
                        str(out)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("title", "numbers", "end"))
    ap.add_argument("--line", default=LINE, help="the title card's line: what existed before and what's new (the FAQ's)")
    ap.add_argument("--out", default=str(ROOT / "film"))
    ap.add_argument("--check", action="store_true", help="print the figures and their files, render nothing")
    args = ap.parse_args()
    figs = figures()
    if args.check:
        for f in figs:
            print(f"{f['big']:>14}  {f['line']}  ({f['from']})")
        return
    cards = {"title": lambda: title(args.line), "numbers": lambda: numbers(figs), "end": end}
    for name, make in cards.items():
        if args.only and name != args.only:
            continue
        body, seconds = make()
        out = Path(args.out) / f"card-{name}.mp4"
        render(body, seconds, out)
        print(f"{out}  ({seconds:.1f} s)")


if __name__ == "__main__":
    main()
