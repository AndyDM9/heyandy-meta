"""The README's pictures of the TV, made again from the demo scenes: one per thing Andy does.

Each scene (scripts/demo_screen.py: drawn pictures, never a home) is shown on the TV's own page, served here, and
screenshot at 1920x1080 once it has settled (after the Reveal, for a find), and cropped to the main card, legible at
the README's width; the public demo is shot whole, answering a typed question. Saved as WebP in
docs/images, so the README shows what the TV shows today.

    uv run python scripts/readme_shots.py                 # every picture
    uv run python scripts/readme_shots.py guide sound     # some
    uv run python scripts/readme_shots.py eyes            # Andy's eyes, finding our cup (downloads DINOv2 once)
    uv run python scripts/readme_shots.py sweep           # Andy's eyes sweeping live, with a camera that's a video
"""
import io
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_screen import show  # noqa: E402

from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

OUT = ROOT / "docs" / "images"
SCENES = {"found": 8.5, "guide": 2.5, "turned": 8.5, "sound": 3.0, "home": 2.5, "told": 2.5, "room": 6.0,
          "mandarin": 9.0, "promises": 2.5}  # settle, s
WHOLE = {"mandarin"}  # the whole TV, not just its card: every label on it is in the language
SIZE = (1920, 1080)
CARD = (590, 240, 1850, 852)  # the TV's main card: what a scene is about, legible small (the captions run the full width)


def save(png: bytes, name: str, width: int = 1280, crop: tuple | None = None) -> Path:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if crop:
        img = img.crop(crop)
    img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    path = OUT / f"{name}.webp"
    img.save(path, "WEBP", quality=88, method=6)
    return path


def tv(names: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    state = ScreenState()
    server = serve(state, port=0)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name in names:
                state.lang, state.language, state.words = "en", "", None  # a scene in another language changes them
                show(state, name)
                page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
                page.goto(url)
                page.wait_for_timeout(SCENES[name] * 1000)
                print(save(page.screenshot(), f"tv-{name}", crop=None if name in WHOLE else CARD))
                page.close()
            browser.close()
    finally:
        server.shutdown()


def demo(question: str = "Where are my keys?") -> None:
    """The public demo (dist/space-static, built by build_static_space.py) answering a typed question."""
    from urllib.parse import quote

    from playwright.sync_api import sync_playwright

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static_space.py")], check=True, capture_output=True)
    server = subprocess.Popen([sys.executable, "-m", "http.server", "8811", "--bind", "127.0.0.1"],
                              cwd=ROOT / "dist" / "space-static", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.0)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
            page.goto(f"http://127.0.0.1:8811/?ask={quote(question)}")
            page.wait_for_timeout(11000)  # "Let me look", the views, then the find and its Reveal
            print(save(page.screenshot(), "demo-ask"))
            browser.close()
    finally:
        server.terminate()


def eyes() -> None:
    """Andy's eyes (eyes.html) finding our cup among look-alikes, DINOv2 running in the browser: the page as a visitor
    sees it, from its Reveal."""
    from playwright.sync_api import sync_playwright

    import socket

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static_space.py")], check=True, capture_output=True)
    with socket.socket() as sock:  # a port nothing else here is using
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                              cwd=ROOT / "dist" / "space-static", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.0)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(f"http://127.0.0.1:{port}/eyes.html?try")
            page.wait_for_function("(document.getElementById('said').textContent || '').startsWith('There')", timeout=300000)
            page.wait_for_timeout(1500)  # the spotlight settles
            print(save(page.screenshot(), "eyes", width=1400))
            browser.close()
    finally:
        server.terminate()


def sweep() -> None:
    """Andy's eyes sweeping live: a camera that's a video sweeping over our museum cups (evals/eyes_live.py), shot
    the moment it's sure enough of a place to look closer, with DINOv2's view in gold and the meter."""
    import functools
    import http.server
    import tempfile
    import threading

    from playwright.sync_api import sync_playwright

    from evals.eyes_live import Quiet, video

    screen = ROOT / "heyandy_meta" / "screen"
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(screen)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            cam = video(Path(tmp) / "sweep.y4m", [screen / "eyes" / "cups.webp"], "wide")
            ctx = p.chromium.launch_persistent_context(
                str(Path(tmp) / "profile"), headless=True, viewport={"width": 1600, "height": 1000}, permissions=["camera"],
                args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", f"--use-file-for-fake-video-capture={cam}"])
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/eyes.html")
            page.wait_for_function("window.EYES_READY === true")
            page.click("#ours1")
            page.wait_for_selector("#known:not([hidden])", timeout=300000)
            page.click("#sweep")
            page.wait_for_function("document.getElementById('said').textContent.startsWith('That looks like it')", timeout=180000)
            page.wait_for_timeout(300)  # sure of a place: "That looks like it. Let me look closer…"
            print(save(page.screenshot(), "eyes-live", width=1400))
            ctx.close()
    finally:
        server.shutdown()


def main() -> None:
    wanted = sys.argv[1:] or [*SCENES, "demo", "eyes", "sweep"]
    tv([n for n in wanted if n in SCENES])
    if "demo" in wanted:
        demo()
    if "eyes" in wanted:
        eyes()
    if "sweep" in wanted:
        sweep()


if __name__ == "__main__":
    main()
