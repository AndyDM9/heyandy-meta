"""The public Space as static files (free for an organisation): the same TV page, with each sample scene saved.

    uv run python scripts/build_static_space.py      # -> dist/space-static/, then: hf upload heyandy-ai/andy ...

Same page and the same rendering code as the robot's TV; only the answers to /state.json are saved in advance, made by
the same demo scenes (scripts/demo_screen.py). No keys, robot code or home pictures: the picture is drawn.
"""
import json
import re
import shutil
import sys
import time
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_screen import SCENES, show  # noqa: E402
from heyandy_meta.screen.server import FONTS, page  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

OUT = ROOT / "dist" / "space-static"
KEYS = re.compile(r"MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}")


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "scenes").mkdir(parents=True)
    (OUT / "fonts").mkdir()
    html = page().replace("<script>", "<script>window.HEYANDY_STATIC = true;</script>\n<script>", 1)
    (OUT / "index.html").write_text(html)
    for name in FONTS:
        (OUT / "fonts" / name).write_bytes(files("heyandy_meta.screen").joinpath("fonts", name).read_bytes())
    shutil.copy(files("heyandy_meta.screen").joinpath("fonts", "OFL.txt"), OUT / "fonts" / "OFL.txt")
    for scene in SCENES:
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
    shutil.copy(ROOT / "docs" / "images" / "sample-drawing.webp", OUT / "drawing.webp")  # the "A picture" scene
    shutil.copy(ROOT / "docs" / "images" / "sample-web.jpg", OUT / "web.jpg")  # the "On the web" scene (Wikipedia)
    for f in OUT.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".json", ".md") and KEYS.search(f.read_text(errors="ignore")):
            raise SystemExit(f"something that looks like a key is in {f}; stopping")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built {OUT} ({size // 1024} KB): index.html, {len(SCENES)} scenes, fonts")


if __name__ == "__main__":
    main()
