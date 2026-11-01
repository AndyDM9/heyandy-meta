"""Andy's eyes in the browser (screen/eyes.html): is it your thing, not just one like it?

Two photos each of eight museum objects (The Met's Open Access, CC0: cups, a jug, teapots, watches, horns), never a
home. For every pair of photos of one object, the first is "your thing" and the second is put on a made-up table among
three others (two look-alike cups always beside the cup); then the same thing on a table of four others, without it;
and, for the four objects in colour, a table with its twin: the other photo with its colours turned half round (a red
mug where yours is blue), which isn't yours.
The page's own search (screen/eyes-core.js, DINOv2 with registers, 8-bit, on the CPU as most visitors run it) runs in
headless Chromium; kept: the closest place, how alike it was, and what Andy would say.

    uv run python -m evals.eyes      # downloads the photos (once) and DINOv2 (once, 24 MB); about 3 minutes
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache" / "heyandy-meta" / "met"
# object -> the photos of it used (0 is the Met's main photo); views of one object differ by side, light or angle
OBJECTS = {2109: [0, 1, 2], 240140: [0, 1, 2], 200114: [0, 1], 8356: [0, 2], 502206: [0, 1], 504065: [0, 1],
           199408: [0, 2], 250230: [0, 1]}
OTHERS = [191578, 207670, 385, 9056, 206812, 845713]  # only ever on the table, never "your thing"

HARNESS = """<!doctype html><meta charset="utf-8"><body><script type="module">
import * as T from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.6";
import * as E from "./eyes-core.js";
const img = (f) => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = "met/" + f + ".jpg"; });
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const center = (i, f = 0.8) => ({ x: i.width * (1 - f) / 2, y: i.height * (1 - f) / 2, w: i.width * f, h: i.height * f });
function table(items) {  // items: [{im, mark, twin}]: a twin is drawn in other colours (its hues turned half round)
  const c = document.createElement("canvas"); c.width = 1280; c.height = 853;
  const g = c.getContext("2d"); const gr = g.createLinearGradient(0, 0, 0, 853);
  gr.addColorStop(0, "#c9b8a0"); gr.addColorStop(1, "#a88f70"); g.fillStyle = gr; g.fillRect(0, 0, 1280, 853);
  const cells = [[0, 0], [1, 0], [0, 1], [1, 1]].sort(() => rnd() - 0.5), placed = [];
  items.forEach((it, k) => {
    const [cx, cy] = cells[k], b = center(it.im, 0.86), s = (230 + rnd() * 150) / Math.max(b.w, b.h);
    const w = b.w * s, h = b.h * s, x = cx * 640 + 20 + rnd() * (600 - w), y = cy * 426 + 10 + rnd() * (406 - h);
    g.filter = it.twin ? "hue-rotate(150deg) saturate(1.4)" : "none";
    g.drawImage(it.im, b.x, b.y, b.w, b.h, x, y, w, h); g.filter = "none"; placed.push({ mark: it.mark, x, y, w, h });
  });
  return { c, placed };
}
const TWINS = [240140, 250230, 504065, 2109];  // in colour: its twin, recoloured, is not yours
window.run = async (groups, pool) => {
  const eyes = await E.load(T); const out = [];
  const on = (placed, at) => (placed.find((p) => at.x >= p.x && at.x <= p.x + p.w && at.y >= p.y && at.y <= p.y + p.h) || {}).mark || null;
  for (const [g, views] of Object.entries(groups)) for (const a of views) for (const b of views) {
    if (a === b) continue;
    const thingIm = await img(`${g}-${a}`), thing = await E.look(eyes, T, thingIm, center(thingIm), 224);
    const others = pool.filter((p) => !p.startsWith(g + "-")).sort(() => rnd() - 0.5);
    if (g === "2109") others.unshift("191578-0", "207670-0");  // cups among cups
    for (const kind of ["with", "without", ...(TWINS.includes(+g) ? ["twin"] : [])]) {
      const names = kind === "without" ? [...new Set(others)].slice(0, 4) : [`${g}-${b}`, ...[...new Set(others)].slice(0, 3)];
      const ims = await Promise.all(names.map(img));
      const { c, placed } = table(ims.map((im, k) => ({ im, mark: names[k], twin: kind === "twin" && k === 0 })));
      const t0 = performance.now();
      const r = await E.find(eyes, T, thing, c, { x: 0, y: 0, w: c.width, h: c.height });
      const box = r.best.box, mid = { x: box.x + box.w / 2, y: box.y + box.h / 2 };
      out.push({ object: +g, yours: a, other: b, table: kind, closest: on(placed, mid), alike: +r.best.whole.toFixed(3),
                 colour: +r.best.colour.toFixed(3), says: r.verdict, right: kind === "with" ? on(placed, mid) === names[0] : null,
                 places: r.candidates.map((x) => [+x.whole.toFixed(3), on(placed, { x: x.box.x + x.box.w / 2, y: x.box.y + x.box.h / 2 })]),
                 seconds: +((performance.now() - t0) / 1000).toFixed(2) });
    }
  }
  return { device: eyes.device, dtype: eyes.dtype, sure: E.SURE, maybe: E.MAYBE, same_colour: E.SAME_COLOUR, out };
};
window.ready = true;
</script>
"""


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "heyandy-eval"}), timeout=60) as r:
        return r.read()


def photos() -> None:
    """The Met's photos of each object, fetched once (public domain only)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    for obj in [*OBJECTS, *OTHERS]:
        views = OBJECTS.get(obj, [0])
        if all((CACHE / f"{obj}-{v}.jpg").exists() for v in views):
            continue
        o = json.loads(get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj}"))
        assert o["isPublicDomain"], obj
        urls = [o["primaryImageSmall"], *[u.replace("/original/", "/web-large/") for u in o["additionalImages"]]]
        for v in views:
            (CACHE / f"{obj}-{v}.jpg").write_bytes(get(urls[v]))


def main() -> None:
    from playwright.sync_api import sync_playwright

    photos()
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        shutil.copytree(CACHE, site / "met")
        shutil.copy(ROOT / "heyandy_meta" / "screen" / "eyes-core.js", site / "eyes-core.js")
        (site / "index.html").write_text(HARNESS)
        server = subprocess.Popen([sys.executable, "-m", "http.server", "8825", "--bind", "127.0.0.1"], cwd=site,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1.0)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto("http://127.0.0.1:8825/")
                page.wait_for_function("window.ready === true", timeout=120000)
                groups = {str(k): v for k, v in OBJECTS.items()}
                pool = [f"{o}-0" for o in OTHERS] + [f"{o}-0" for o in OBJECTS]
                r = page.evaluate("([g, p]) => run(g, p)", [groups, pool])
                browser.close()
        finally:
            server.terminate()
    rows = r["out"]
    with_ = [x for x in rows if x["table"] == "with"]
    without = [x for x in rows if x["table"] == "without"]
    strong = [x for x in rows if x["table"] == "twin" and x["object"] != 2109]
    white = [x for x in rows if x["table"] == "twin" and x["object"] == 2109]  # mostly white: its twin is too
    summary = {
        "tables with it": len(with_), "closest was it": sum(x["right"] for x in with_),
        "found, and right": sum(x["right"] and x["says"] == "found" for x in with_),
        "found, but wrong": sum(not x["right"] and x["says"] == "found" for x in with_),
        "asked (maybe)": sum(x["says"] == "maybe" for x in with_),
        "tables without it": len(without), "said found": sum(x["says"] == "found" for x in without),
        "asked (maybe) without it": sum(x["says"] == "maybe" for x in without),
        "highest alike without it": max(x["alike"] for x in without),
        "tables with its twin in strong colours (not it)": len(strong),
        "said found of a twin in strong colours": sum(x["says"] == "found" for x in strong),
        "tables with the white cup's twin (only its painted flowers recoloured)": len(white),
        "said found of the white cup's twin": sum(x["says"] == "found" for x in white),
        "colour of the right one, lowest": min(x["colour"] for x in with_ if x["right"]),
        "colour of a twin in strong colours, highest": max(x["colour"] for x in strong) if strong else None,
        "seconds, median": sorted(x["seconds"] for x in rows)[len(rows) // 2],
    }
    out = ROOT / "evals" / "results" / f"eyes-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "device": r["device"], "dtype": r["dtype"],
                               "sure": r["sure"], "maybe": r["maybe"], "same_colour": r["same_colour"], "summary": summary,
                               "photos": "The Metropolitan Museum of Art, Open Access (CC0), objects "
                                         + ", ".join(map(str, [*OBJECTS, *OTHERS])), "tables": rows}, indent=1))
    print(json.dumps(summary, indent=1))
    for x in rows:
        print(x["table"], x["object"], x["yours"], x["other"], x["alike"], x["colour"], x["says"], x["right"], x["places"])
    print(f"saved {out}")


if __name__ == "__main__":
    main()
