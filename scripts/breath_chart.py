"""The picture of the night Andy listened to its own breathing: the Rayleigh test's z at every rate from 0.15 to 0.30 a
second, over the night's sounds (their times only, evals/ego_noise.py), one spike at the breath's own rate.

For sharing (1200 by 675, X's size) and the README: made from the journal on this computer, the figures it shows kept
in the PNG's metadata as the social card does.

    uv run python scripts/breath_chart.py      # -> docs/images/breath-spike.png
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "images" / "breath-spike.png"
SIZE = (1200, 675)
NIGHT = ("2026-11-02 00:00", "2026-11-02 05:30")
LO, HI, STEP = 0.15, 0.30, 0.0001
ALT = ("A line chart: the Rayleigh z of the night's sounds against rate, 0.15 to 0.30 a second. Flat near zero "
       "everywhere except one spike at 0.22 a second, Andy's own breath.")


def curve(times: list[float]) -> list[tuple[float, float]]:
    from evals.ego_noise import rayleigh

    n = int(round((HI - LO) / STEP)) + 1
    return [(LO + i * STEP, rayleigh(times, LO + i * STEP, 2)[1]) for i in range(n)]


def svg(points: list[tuple[float, float]], hz: float, w: int = 990, h: int = 280) -> tuple[str, dict]:
    """The chart alone: a line of z against rate, its one spike labelled, the axes recessive."""
    top = max(z for _, z in points)
    x = lambda f: (f - LO) / (HI - LO) * w  # noqa: E731
    y = lambda z: h - z / top * h  # noqa: E731
    line = " ".join(f"{x(f):.1f},{y(z):.1f}" for f, z in points)
    peak = max(points, key=lambda p: p[1])
    other = max(z for f, z in points if abs(f - hz) > STEP / 2)
    ticks = "".join(f'<line x1="{x(f):.1f}" y1="{h}" x2="{x(f):.1f}" y2="{h + 8}" class="axis"/>'
                    f'<text x="{x(f):.1f}" y="{h + 32}" class="tick" text-anchor="middle">{f:.2f}</text>'
                    for f in (0.15, 0.18, 0.21, 0.24, 0.27, 0.30))
    return f"""<svg width="{w + 80}" height="{h + 70}" viewBox="-60 -20 {w + 80} {h + 70}" xmlns="http://www.w3.org/2000/svg">
<line x1="0" y1="{h}" x2="{w}" y2="{h}" class="axis"/>{ticks}
<line x1="0" y1="{y(top):.1f}" x2="{w}" y2="{y(top):.1f}" class="grid"/>
<text x="-12" y="{y(top) + 6:.1f}" class="tick" text-anchor="end">{top:,.0f}</text>
<text x="-12" y="{h + 6}" class="tick" text-anchor="end">0</text>
<polyline points="{line}" class="line"/>
<circle cx="{x(peak[0]):.1f}" cy="{y(peak[1]):.1f}" r="7" class="dot"/>
<text x="{x(peak[0]) + 18:.1f}" y="{y(peak[1]) + 8:.1f}" class="label"><tspan class="strong">{peak[0]:.2f} breaths a second:</tspan> Andy's own, z {peak[1]:,.0f}</text>
<text x="{w}" y="{h - 16}" class="label" text-anchor="end">every other rate: {other:.0f} at most</text>
<text x="{w / 2:.1f}" y="{h + 62}" class="tick" text-anchor="middle">breaths a second, each rate tested (the z of the sounds' phase, twice a breath)</text>
</svg>""", {"peak at": round(peak[0], 4), "z": round(peak[1]), "any other rate, at most": round(other, 1)}


def html(chart: str, per_hour: int) -> str:
    font = (ROOT / "heyandy_meta" / "screen" / "fonts" / "AtkinsonHyperlegibleNext.ttf").as_uri()
    mono = (ROOT / "heyandy_meta" / "screen" / "fonts" / "AtkinsonHyperlegibleMono.ttf").as_uri()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Next; src: url("{font}"); font-weight: 200 900; }}
@font-face {{ font-family: Mono; src: url("{mono}"); font-weight: 200 900; }}
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: {SIZE[0]}px; height: {SIZE[1]}px; overflow: hidden; }}
body {{ font-family: Next, sans-serif; color: #f5f3ef; background: #12241d; padding: 44px 64px 0; }}
h1 {{ font-size: 44px; line-height: 1.08; font-weight: 800; letter-spacing: -0.4px; }}
h1 em {{ font-style: normal; color: #ffcf5c; }}
p {{ margin-top: 14px; font-size: 22px; line-height: 1.32; color: #cfe3d9; max-width: 1060px; }}
svg {{ display: block; margin: 22px 0 0 8px; overflow: visible; }}
.axis {{ stroke: #9fb8ad; stroke-width: 1.5; }}
.grid {{ stroke: #2c4a3d; stroke-width: 1; stroke-dasharray: 4 6; }}
.tick {{ font-family: Mono, monospace; font-size: 17px; fill: #9fb8ad; }}
.line {{ fill: none; stroke: #ffcf5c; stroke-width: 2; stroke-linejoin: round; }}
.dot {{ fill: #ffcf5c; stroke: #12241d; stroke-width: 2; }}
.label {{ font-size: 21px; fill: #f5f3ef; }}
.strong {{ font-weight: 800; }}
.foot {{ position: absolute; left: 64px; right: 64px; bottom: 22px; font-size: 17px; color: #9fb8ad;
         display: flex; justify-content: space-between; }}
</style></head><body>
<h1>Our robot spent the night <em>listening to itself breathe.</em></h1>
<p>{per_hour:,} sounds an hour, all night, not one of them for it. We never record, so we tested the sounds' times alone against every
rate, and they kept time with one: its own breathing.</p>
{chart}
<div class="foot"><span>HeyAndy · evals/ego_noise.py · November 2, midnight to 5:30</span><span>Now Andy rests when nobody's there</span></div>
</body></html>"""


def render(out: Path = OUT) -> dict:
    from playwright.sync_api import sync_playwright

    from evals.ego_noise import journal, sounds
    from heyandy_meta.robot.motion import Motion

    found = sounds(journal(*NIGHT))
    if not found:
        raise SystemExit("no sounds in the journal for that night (it's kept only so long)")
    times = [t for t, _, _ in found]
    chart, figures = svg(curve(times), Motion().breathe_hz)
    figures["sounds an hour"] = round(len(found) / 5.5)
    page_file = ROOT / "dist" / "breath-spike.html"
    page_file.parent.mkdir(exist_ok=True)
    page_file.write_text(html(chart, figures["sounds an hour"]))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        page.goto(page_file.as_uri())
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(out), type="png")
        browser.close()
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("figures", json.dumps(figures))
    info.add_text("Description", ALT)
    Image.open(out).convert("RGB").save(out, "PNG", optimize=True, pnginfo=info)
    return figures


if __name__ == "__main__":
    print(render(), OUT)
