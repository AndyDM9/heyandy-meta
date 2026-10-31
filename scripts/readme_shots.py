"""The README's pictures of the TV, made again from the demo scenes: one per thing Andy does.

Each scene (scripts/demo_screen.py: drawn pictures, never a home) is shown on the TV's own page, served here, and
screenshot at 1920x1080 once it has settled (after the Reveal, for a find), and cropped to the main card, legible at
the README's width; the public demo is shot whole, answering a typed question. Saved as WebP in
docs/images, so the README shows what the TV shows today.

    uv run python scripts/readme_shots.py                 # every picture
    uv run python scripts/readme_shots.py guide sound     # some
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
SCENES = {"found": 8.5, "guide": 2.5, "turned": 8.5, "sound": 3.0, "home": 2.5, "told": 2.5, "room": 6.0}  # settle, s
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
                show(state, name)
                page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
                page.goto(url)
                page.wait_for_timeout(SCENES[name] * 1000)
                print(save(page.screenshot(), f"tv-{name}", crop=CARD))
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


def main() -> None:
    wanted = sys.argv[1:] or [*SCENES, "demo"]
    tv([n for n in wanted if n in SCENES])
    if "demo" in wanted:
        demo()


if __name__ == "__main__":
    main()
