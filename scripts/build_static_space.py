"""The public Space as static files (free for an organisation): the same TV page, with each sample scene saved.

    uv run python scripts/build_static_space.py      # -> dist/space-static/, then: hf upload heyandy-ai/andy ...

Same page and the same rendering code as the robot's TV; only the answers to /state.json are saved in advance, made by
the same demo scenes (scripts/demo_screen.py). No keys, robot code or home pictures: the picture is drawn.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The browser's libraries, also served from the Space itself, for when their CDN can't be reached (down, or blocked on
# a visitor's network): fetched once into a cache and checked by SHA-256, so a build never ships other bytes. The CDN
# stays first: it sends them compressed (the runtime 4 MB), where the Space sends its own copy whole (22 MB).
CDN = "https://cdn.jsdelivr.net/npm/"
VENDOR = {
    "transformers.min.js": ("@huggingface/transformers@3.7.6/dist/transformers.min.js",
                            "13746ae88695b62e431fc5ebe3beb10a080d2081406047670639ce8c10a9ba25"),
    "ort-wasm-simd-threaded.jsep.mjs": ("@huggingface/transformers@3.7.6/dist/ort-wasm-simd-threaded.jsep.mjs",
                                        "08fb86ec433c78bfb032c5d84a68b8e8e5a8d81268fa39e24314179a5767a5b9"),
    "ort-wasm-simd-threaded.jsep.wasm": ("@huggingface/transformers@3.7.6/dist/ort-wasm-simd-threaded.jsep.wasm",
                                         "c46655e8a94afc45338d4cb2b840475f88e5012d524509916e505079c00bfa39"),
    "qrcode.js": ("qrcode-generator@1.4.4/qrcode.js", "18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780"),
}
CACHE = Path.home() / ".cache" / "heyandy-meta" / "vendor"


def vendored(name: str, fetch=None) -> bytes:
    """One library file, from the cache or the CDN, only if its SHA-256 is the one recorded here."""
    import hashlib
    import urllib.request

    path, digest = VENDOR[name]
    cached = CACHE / name
    data = cached.read_bytes() if cached.exists() else None
    if data is None or hashlib.sha256(data).hexdigest() != digest:
        data = (fetch or (lambda u: urllib.request.urlopen(u, timeout=60).read()))(CDN + path)
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"{name} from {CDN + path} isn't the file recorded (SHA-256 differs): not building with it")
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_screen import IN_LANGUAGE, SCENES, sample_room, show  # noqa: E402
from heyandy_meta.screen.server import FONTS, page  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

OUT = ROOT / "dist" / "space-static"
KEYS = re.compile(r"MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}")
HOST = "https://heyandy-ai-andy.static.hf.space"  # the Space's own address (its pages, and the card)
SPACE_URL = "https://huggingface.co/spaces/heyandy-ai/andy"
# What a shared link to each page says, with the card (scripts/social_card.py): (title, description, the page's address)
SHARED = {
    "index.html": ("Andy: finds what you've lost, and points at it",
                   "The TV beside Andy, a tabletop robot built on Meta's models: a 75-second story, then ask it yourself. "
                   "Your home's pictures and voice stay in your home.", SPACE_URL),
    "eyes.html": ("Andy's eyes, on your things",
                  "Show Andy's eyes your mug once, then sweep your phone round the room: Meta's DINOv2 in your browser. "
                  "Nothing leaves it.", f"{HOST}/eyes.html"),
    "hood.html": ("Under the hood · Andy", "A search on the robot, stage by stage, and which of Meta's models did each.",
                  f"{HOST}/hood.html"),
}


def shared(html: str, name: str) -> str:
    """The page's description, and the card a shared link shows (Open Graph, read by X, LinkedIn, Slack and the rest)."""
    from html import escape

    from social_card import ALT, SIZE

    title, description, url = SHARED[name]
    tags = [f'<meta name="description" content="{escape(description)}">',
            '<meta property="og:type" content="website">', '<meta property="og:site_name" content="HeyAndy">',
            f'<meta property="og:title" content="{escape(title)}">',
            f'<meta property="og:description" content="{escape(description)}">',
            f'<meta property="og:url" content="{url}">', f'<meta property="og:image" content="{HOST}/card.png">',
            f'<meta property="og:image:width" content="{SIZE[0]}">', f'<meta property="og:image:height" content="{SIZE[1]}">',
            f'<meta property="og:image:alt" content="{escape(ALT)}">', '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:image:alt" content="{escape(ALT)}">']
    return html.replace("</title>", "</title>\n" + "\n".join(tags), 1)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="", help="the 3-minute video's link, for the story's end card")
    ap.add_argument("--clip", type=Path, help="a short clip of the robot (MP4, muted, about 10 s): the story's first chapter")
    ap.add_argument("--clip-caption", default="Filmed on the robot · uncut · 1× speed")
    args = ap.parse_args()
    video = args.video
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "scenes").mkdir(parents=True)
    (OUT / "fonts").mkdir()
    flags = "window.HEYANDY_STATIC = true;" + (f" window.HEYANDY_VIDEO = {json.dumps(video)};" if video else "")
    if args.clip:  # the robot itself, filmed: kept small, for a page anyone opens
        size = args.clip.stat().st_size
        if size > 15_000_000:
            raise SystemExit(f"{args.clip} is {size / 1e6:.0f} MB: cut it to about 10 s at 720p (make_film.py burn --shape wide)")
        seconds = float(subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        str(args.clip)], capture_output=True, text=True).stdout.strip() or 10)
        flags += (f" window.HEYANDY_CLIP = 'robot.mp4'; window.HEYANDY_CLIP_SECONDS = {min(20.0, round(seconds, 1))};"
                  f" window.HEYANDY_CLIP_CAPTION = {json.dumps(args.clip_caption)};")
    html = page().replace("<script>", f"<script>{flags}</script>\n<script>", 1)
    (OUT / "index.html").write_text(shared(html, "index.html"))
    for name in FONTS:
        (OUT / "fonts" / name).write_bytes(files("heyandy_meta.screen").joinpath("fonts", name).read_bytes())
    shutil.copy(files("heyandy_meta.screen").joinpath("fonts", "OFL.txt"), OUT / "fonts" / "OFL.txt")
    for scene in (*SCENES, *IN_LANGUAGE):  # the language scenes too: played by Ask Andy, not on the bar
        state = ScreenState()
        show(state, scene)
        snap = state.snapshot()
        snap["demo"] = list(SCENES)
        if snap.get("next"):
            snap["next"] = {"text": snap["next"]["text"], "in_s": round(snap["next"]["at"] - time.time())}
        (OUT / "scenes" / f"{scene}.json").write_text(json.dumps(snap))
    readme = (ROOT / "space" / "README.md").read_text()
    readme = readme.replace("sdk: docker\napp_port: 7860\n", "sdk: static\napp_file: index.html\n")
    (OUT / "README.md").write_text(readme)
    shutil.copy(ROOT / "LICENSE", OUT / "LICENSE")
    if args.clip:
        shutil.copy(args.clip, OUT / "robot.mp4")
    shutil.copy(ROOT / "docs" / "images" / "sample-drawing.webp", OUT / "drawing.webp")  # the "A picture" scene
    shutil.copy(ROOT / "docs" / "images" / "sample-web.jpg", OUT / "web.jpg")  # the "On the web" scene (Wikipedia)
    (OUT / "room.bin").write_bytes(sample_room()[0])  # the "room" scene: a made-up room's shape
    # under the hood: the page, and a sample of turns timed on the robot (it says it's a sample)
    (OUT / "hood.html").write_text(shared(files("heyandy_meta.screen").joinpath("hood.html").read_text(), "hood.html"))
    sample = json.loads(files("heyandy_meta.screen").joinpath("hood_sample.json").read_text())
    (OUT / "hood.json").write_text(json.dumps({**sample, "sample": True}))
    # Andy's eyes, on the visitor's own things: DINOv2 in the browser, and our cups for anyone without a photo
    (OUT / "eyes.html").write_text(shared(files("heyandy_meta.screen").joinpath("eyes.html").read_text(), "eyes.html"))
    shutil.copy(ROOT / "docs" / "images" / "social-card.png", OUT / "card.png")  # what a shared link shows
    (OUT / "eyes-core.js").write_text(files("heyandy_meta.screen").joinpath("eyes-core.js").read_text())
    (OUT / "eyes").mkdir()
    (OUT / "vendor").mkdir()
    for name in VENDOR:  # the libraries' fallback copies, checked
        (OUT / "vendor" / name).write_bytes(vendored(name))
    for name in ("cup.webp", "cups.webp", "cups-without.webp", "CREDITS.txt"):
        (OUT / "eyes" / name).write_bytes(files("heyandy_meta.screen").joinpath("eyes", name).read_bytes())
    for f in OUT.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".json", ".md", ".js") and KEYS.search(f.read_text(errors="ignore")):
            raise SystemExit(f"something that looks like a key is in {f}; stopping")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built {OUT} ({size // 1024} KB): index.html, {len(SCENES)} scenes, fonts")


if __name__ == "__main__":
    main()
