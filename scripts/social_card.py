"""The picture a shared link shows: Andy's card for X, LinkedIn, Slack, Discord and GitHub (1280x640, under 1 MB).

Posted, the Space's link shows its `thumbnail:` (space/README.md, set by the build) instead of Hugging Face's generic
card; a link straight to the Space's pages shows it too (their og:image); and GitHub shows it once it's the repository's
social preview (Settings -> Social preview, by hand: there's no API for it). 2:1 is what X's large card and GitHub ask
for. Its figures are made where the documents' are (scripts/claims.py, the code, the submission's model table), so the
card says what they say on the day it's made; its picture is the TV's own drawn demo scene, never a home.

    uv run python scripts/social_card.py          # -> docs/images/social-card.png
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "images" / "social-card.png"
SIZE = (1280, 640)
SPACE = "huggingface.co/spaces/heyandy-ai/andy"
ALT = ("Andy, a tabletop robot built on Meta's models: it finds what you've lost and points at it. Beside the words, "
       "its TV at the moment of a find (a drawn demo scene).")


def models() -> list[str]:
    """Meta's models Andy runs, as the submission's table names them (two to a row in some rows)."""
    text = (ROOT / "docs" / "submission.md").read_text()
    table = text.split("| Model |", 1)[1].split("\n\n", 1)[0]
    return [name for row in table.splitlines()[2:] for name in re.findall(r"\*\*([^*]+)\*\*", row.split("|")[1])]


def figures() -> list[tuple[str, str]]:
    """(big, small) for the card: each made from its source."""
    import claims
    from heyandy_meta.companion.language import LANGUAGES

    pointed = claims.unattended_since_fix().removesuffix(" unattended searches")
    return [(pointed, "searches on the robot ended in a point"),
            (str(len(LANGUAGES)), "languages it hears and speaks"),
            (str(len(models())), "models, and every one is Meta's")]


def html() -> str:
    font = (ROOT / "heyandy_meta" / "screen" / "fonts" / "AtkinsonHyperlegibleNext.ttf").as_uri()
    mono = (ROOT / "heyandy_meta" / "screen" / "fonts" / "AtkinsonHyperlegibleMono.ttf").as_uri()
    sign = (ROOT / "docs" / "images" / "heyandy-signature-reversed.svg").as_uri()
    tv = (ROOT / "docs" / "images" / "tv-found.webp").as_uri()
    tiles = "".join(f'<div class="fig"><b>{big}</b><span>{small}</span></div>' for big, small in figures())
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Next; src: url("{font}"); font-weight: 200 900; }}
@font-face {{ font-family: Mono; src: url("{mono}"); font-weight: 200 900; }}
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: {SIZE[0]}px; height: {SIZE[1]}px; overflow: hidden; }}
body {{ font-family: Next, sans-serif; color: #f5f3ef; position: relative;
       background: radial-gradient(900px 520px at 88% 30%, #1e5f4a 0%, #12241d 62%), #12241d; }}
.sign {{ position: absolute; left: 64px; top: 52px; width: 210px; }}
h1 {{ position: absolute; left: 64px; top: 112px; width: 640px; font-size: 58px; line-height: 1.06;
      font-weight: 800; letter-spacing: -0.5px; }}
h1 em {{ font-style: normal; color: #ffcf5c; }}
.sub {{ position: absolute; left: 64px; top: 330px; width: 600px; font-size: 25px; line-height: 1.3; color: #cfe3d9; }}
.figs {{ position: absolute; left: 64px; top: 432px; display: flex; gap: 44px; }}
.fig {{ flex: none; }}
.fig b {{ display: block; font-family: Mono, monospace; font-size: 42px; font-weight: 700; color: #ffcf5c;
          white-space: nowrap; }}
.fig span {{ display: block; margin-top: 6px; max-width: 200px; font-size: 19px; line-height: 1.25; color: #cfe3d9; }}
.tv {{ position: absolute; left: 728px; top: 150px; width: 500px; border-radius: 22px; overflow: hidden;
       border: 8px solid #0b1813; box-shadow: 0 28px 70px rgba(0, 0, 0, 0.55); transform: rotate(-2deg); }}
.tv img {{ display: block; width: 100%; }}
.foot {{ position: absolute; left: 64px; right: 64px; bottom: 34px; font-size: 18px; color: #9fb8ad;
         display: flex; justify-content: space-between; }}
.foot b {{ color: #f5f3ef; font-weight: 700; }}
</style></head><body>
<img class="sign" src="{sign}" alt="HeyAndy">
<h1>Andy finds what you've lost, and <em>points at it.</em></h1>
<p class="sub">A tabletop robot built on Meta's models. Your home's pictures and voice stay in your home.</p>
<div class="figs">{tiles}</div>
<div class="tv"><img src="{tv}" alt=""></div>
<div class="foot"><span><b>{SPACE}</b></span><span>HeyAndy, Inc. · Meta's Global AI Developer Hackathon</span></div>
</body></html>"""


def render(out: Path = OUT) -> Path:
    from playwright.sync_api import sync_playwright

    page_file = ROOT / "dist" / "social-card.html"
    page_file.parent.mkdir(exist_ok=True)
    page_file.write_text(html())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        page.goto(page_file.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
        page.screenshot(path=str(out), type="png")
        browser.close()
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()  # what it says, kept in the file, so a test knows when the scorecards have moved on
    info.add_text("figures", json.dumps(figures()))
    info.add_text("Description", ALT)
    Image.open(out).convert("RGB").save(out, "PNG", optimize=True, pnginfo=info)
    return out


def said(path: Path = OUT) -> list:
    """The figures a made card shows, as it recorded them."""
    from PIL import Image

    return json.loads(Image.open(path).text.get("figures", "[]"))


if __name__ == "__main__":
    out = render()
    print(f"wrote {out} ({out.stat().st_size // 1024} KB): {', '.join(b + ' ' + s for b, s in figures())}")
