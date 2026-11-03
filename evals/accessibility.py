"""Andy's public pages, checked for people who see less well or tap less surely.

axe-core (Deque's checker for WCAG 2.2 A and AA, and its best practices) runs in Chromium on every scene of the TV
page, its story and end card, Andy's eyes, and under the hood, at a desktop's width and a phone's. Where axe can't
decide a text's contrast (text over a gradient, a picture or another element), it's measured from the pixels: the
text is hidden, what's behind it photographed, and its colour (with its transparency) compared with each pixel; the
5th-percentile pixel decides, so a stray border doesn't, and the worst is kept too. WCAG's thresholds: 4.5:1, or 3:1
for large text (24 px, or 18.66 px bold). Only counts, rule names and selectors are kept.

    uv run python -m evals.accessibility          # builds nothing: run scripts/build_static_space.py first
"""
import functools
import hashlib
import http.server
import json
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILT = ROOT / "dist" / "space-static"
AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
AXE_SHA256 = "b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3"
AXE_CACHE = Path.home() / ".cache" / "heyandy-meta" / "vendor" / "axe.min.js"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
WIDTHS = {"desktop": (1600, 900), "phone": (390, 844)}


def axe(fetch=None) -> str:
    """axe-core, from the cache or its CDN, only if it's the file recorded here (never shipped with the Space)."""
    data = AXE_CACHE.read_bytes() if AXE_CACHE.exists() else None
    if data is None or hashlib.sha256(data).hexdigest() != AXE_SHA256:
        data = (fetch or (lambda u: urllib.request.urlopen(u, timeout=60).read()))(AXE_URL)
        if hashlib.sha256(data).hexdigest() != AXE_SHA256:
            raise SystemExit(f"{AXE_URL} isn't the file recorded (SHA-256 differs)")
        AXE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        AXE_CACHE.write_bytes(data)
    return data.decode()


def luminance(rgb) -> float:
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def measured(fg: tuple, alpha: float, pixels: list[tuple]) -> tuple[float, float]:
    """The text's contrast against what's behind it: (5th percentile, worst), its colour laid over each pixel."""
    out = sorted(ratio(tuple(alpha * f + (1 - alpha) * p for f, p in zip(fg, px)), px) for px in pixels)
    return out[len(out) // 20], out[0]


def large(size_px: float, weight: int) -> bool:
    return size_px >= 24 or (size_px >= 18.66 and weight >= 700)


# In the page: an element brought into view; its text colour (SVG text's fill), with its alpha times every ancestor's
# opacity; its size and weight; its box in the viewport; and whether something else covers it (then nobody sees it)
DESCRIBE = """sel => { const e = document.querySelector(sel); if (!e) return null;
  e.scrollIntoView({block: "center", inline: "center"});
  const s = getComputedStyle(e), svg = e instanceof SVGElement;
  const m = (svg ? s.fill : s.color).match(/[\\d.]+/g); if (!m) return null;
  const c = m.map(Number); let a = c.length > 3 ? c[3] : 1;
  for (let p = e; p; p = p.parentElement) a *= Number(getComputedStyle(p).opacity);
  // each line of its own text, as drawn (a quote that wraps, a pill's border, a swatch beside a label: not text)
  const lines = [], walk = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
  for (let n; (n = walk.nextNode()); ) {
    if (!n.textContent.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    for (const q of range.getClientRects()) lines.push(q);
  }
  if (!lines.length) lines.push(e.getBoundingClientRect());  // an input's words aren't text in the page
  const boxes = [];
  for (const q of lines.slice(0, 6)) {
    const inset = q.height * 0.15;  // the middle of the line, where the letters are (not a pill's border round them)
    const x0 = Math.max(0, q.left), y0 = Math.max(0, q.top + inset), x1 = Math.min(innerWidth, q.right),
          y1 = Math.min(innerHeight, q.bottom - inset);
    if (x1 - x0 < 2 || y1 - y0 < 2) continue;
    const hit = document.elementFromPoint((x0 + x1) / 2, (y0 + y1) / 2);  // something else over it: nobody sees it
    if (hit && (hit === e || e.contains(hit) || hit.contains(e))) boxes.push({x: x0, y: y0, width: x1 - x0, height: y1 - y0});
  }
  if (!boxes.length) return null;
  const b = s.backgroundColor.match(/[\\d.]+/g).map(Number);  // its own solid background, if it has one: the text's
  let own = !svg && s.backgroundImage === "none" && (b.length < 4 || b[3] === 1) ? b.slice(0, 3) : null;
  const k = (s.stroke || "").match(/[\\d.]+/g);  // SVG text with a halo (an opaque stroke painted first): that's its background
  if (svg && k && s.paintOrder.startsWith("stroke") && parseFloat(s.strokeWidth) >= 2 && (k.length < 4 || Number(k[3]) === 1))
    own = k.slice(0, 3).map(Number);
  return {fg: c.slice(0, 3), alpha: a, size: parseFloat(s.fontSize), weight: Number(s.fontWeight) || 400, own, boxes}; }"""
HIDE = """sel => { const e = document.querySelector(sel); e.setAttribute("data-unseen", "");
  if (!document.getElementById("unseen")) { const st = document.createElement("style"); st.id = "unseen";
    st.textContent = "[data-unseen], [data-unseen] * { color: transparent !important; fill: transparent !important; " +
      "text-shadow: none !important; caret-color: transparent !important; " +
      "-webkit-text-fill-color: transparent !important } [data-unseen]::placeholder { color: transparent !important }";
    document.head.append(st); } }"""
SHOW = """sel => document.querySelector(sel)?.removeAttribute("data-unseen")"""


def contrast_of(page, selector: str) -> dict | None:
    """One element's text measured over its own background, from a photograph of what's behind each of its lines;
    None when nobody can see it (covered by something else, or off the page)."""
    from io import BytesIO

    from PIL import Image

    d = page.evaluate(DESCRIBE, selector)
    if not d:
        return None
    if d["own"]:  # on its own solid background (a tick in its green circle): that's what's behind the text
        pixels = [tuple(d["own"])]
    else:  # photographed as it is now (not with animations finished: a find's dark spotlight ends by fading out)
        page.evaluate(HIDE, selector)
        try:
            shots = [page.screenshot(clip=box) for box in d["boxes"]]
        finally:
            page.evaluate(SHOW, selector)
        pixels = []
        for shot in shots:
            img = Image.open(BytesIO(shot)).convert("RGB")
            img.thumbnail((160, 160))
            pixels += list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
    p5, worst = measured(tuple(d["fg"]), d["alpha"], pixels)
    need = 3.0 if large(d["size"], d["weight"]) else 4.5
    return {"selector": selector, "ratio": round(p5, 2), "worst": round(worst, 2), "needs": need,
            "size_px": d["size"], "ok": p5 >= need}


def check(page, axe_js: str) -> dict:
    """axe on the page as it is, and the contrast it couldn't decide measured."""
    page.add_script_tag(content=axe_js)
    r = page.evaluate("tags => axe.run(document, {runOnly: {type: 'tag', values: tags}, resultTypes: "
                      "['violations', 'incomplete']})", TAGS)
    review = [n["target"][0] for v in r["incomplete"] if v["id"] == "color-contrast" for n in v["nodes"]
              if isinstance(n["target"][0], str)]
    measures = []
    for sel in dict.fromkeys(review):
        m = contrast_of(page, sel)
        if m and not m["ok"]:  # a page that redraws itself (under the hood, every second): a real fault fails twice
            page.wait_for_timeout(400)
            again = contrast_of(page, sel)
            m = again if again and again["ratio"] > m["ratio"] else m
        if m:
            measures.append(m)
    return {"violations": {v["id"]: [n["target"][0] for n in v["nodes"]][:8] for v in r["violations"]},
            "passed rules": len(r["passes"]) if "passes" in r else None,
            "contrast measured": len(measures), "contrast too low": [m for m in measures if not m["ok"]]}


def serve(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def states() -> list[tuple[str, str, str | None]]:
    """(name, path, what to run after loading): the front door, the story, its end card, each scene, Andy's eyes,
    under the hood."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from demo_screen import SCENES

    return ([("welcome", "index.html", None),
             ("welcome, Andy speaking", "index.html", "document.querySelector('#welcome .bubble').classList.add('own')"),
             ("welcome, choosing a language", "index.html", "document.querySelector('#welcome .langbtn').click()"),
             ("story", "index.html?story", None),
             # told in another of Andy's languages: Arabic, right to left, where it's built, else another script
             ("story, in the visitor's language", "index.html?story",
              "exploreAll(); toldChoice = ['ar', 'hi', 'ko', 'ru', 'uk'].find(c => NARRATION_IN[c]) || null; startStory()"),
             ("end card", "index.html?story", "endCard()")]
            + [(f"scene: {s}", f"index.html?scene={s}", None) for s in SCENES]
            + [("Andy's eyes", "eyes.html", None), ("Andy, measured", "proof.html", None), ("under the hood", "hood.html", None),
               ("under the hood, playing back", "hood.html", "window.hoodReplay(0.003)")])  # held near its start


# The page as it rests: every animation with an end (a fade in, a find's spotlight) waited out, the endless ones (the
# background's slow drift) paused, so a photograph and the colours read from the page are of the same moment
SETTLE = """async () => {
  const ends = a => a.effect && a.effect.getComputedTiming().endTime !== Infinity;
  for (let i = 0; i < 3; i++) {
    const running = document.getAnimations().filter(a => ends(a) && a.playState !== "finished");
    if (!running.length) break;
    await Promise.race([Promise.all(running.map(a => a.finished.catch(() => null))), new Promise(r => setTimeout(r, 12000))]);
  }
  document.getAnimations().forEach(a => { if (!ends(a)) a.pause(); });
  try { if (story) story.paused = true; } catch (e) {} }"""  # the TV page's story: held on its chapter


def audit(base: str, axe_js: str, which=None, widths=WIDTHS) -> list[dict]:
    """Each state at each width: axe, and the contrast it couldn't decide, measured."""
    from playwright.sync_api import sync_playwright

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, path, then in which or states():
            for width, (w, h) in widths.items():
                page = browser.new_page(viewport={"width": w, "height": h}, reduced_motion="reduce")
                page.goto(base + path)
                page.wait_for_timeout(1500)
                if then:
                    page.evaluate(then)
                    page.wait_for_timeout(500)
                page.evaluate(SETTLE)
                row = {"state": name, "width": width, **check(page, axe_js)}
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("state", "width", "violations", "contrast measured")}
                                 | {"too low": [(m["selector"], m["ratio"]) for m in row["contrast too low"]]},
                                 ensure_ascii=False), flush=True)
                page.close()
        browser.close()
    return rows


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="states whose name has this in it (a quick look; not saved)")
    args = ap.parse_args()
    if not (BUILT / "index.html").exists():
        raise SystemExit("build the Space first: uv run python scripts/build_static_space.py")
    server, base = serve(BUILT)
    try:
        rows = audit(base, axe(), [s for s in states() if args.only in s[0]] if args.only else None)
    finally:
        server.shutdown()
    low = [dict(m, state=r["state"], width=r["width"]) for r in rows for m in r["contrast too low"]]
    summary = {"pages and states": len(rows), "with an axe violation": sum(bool(r["violations"]) for r in rows),
               "rules violated": sorted({k for r in rows for k in r["violations"]}),
               "texts measured from pixels": sum(r["contrast measured"] for r in rows),
               "texts below WCAG AA contrast": len(low),
               "below, distinct": sorted({m["selector"] for m in low})}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    if args.only:
        return
    out = ROOT / "evals" / "results" / f"accessibility-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "axe": AXE_URL.rsplit("/", 2)[-2],
                               "tags": TAGS, "summary": summary, "states": rows}, indent=1, ensure_ascii=False))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
