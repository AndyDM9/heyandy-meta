"""Andy's eyes (screen/eyes.html) in a real browser, with no network: the page runs, says plainly when DINOv2 can't be
fetched, and its search (screen/eyes-core.js) finds a thing's squares put among others. The model itself is measured
in evals/eyes.py. Skipped where Playwright's Chromium isn't installed."""
import functools
import http.server
import threading
from importlib.resources import files

import pytest

playwright = pytest.importorskip("playwright.sync_api")

SCREEN = str(files("heyandy_meta.screen"))


@pytest.fixture(scope="module")
def site():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SCREEN)
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def page(site):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # noqa: BLE001 - no browser here: skip
            pytest.skip(f"no Chromium for Playwright: {e}")
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(site) else r.continue_())  # no network
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(f"{site}/eyes.html")
        pg.wait_for_function("window.EYES_READY === true", timeout=10000)
        yield pg
        browser.close()


def test_the_page_runs_and_waits_for_your_thing_before_looking(page):
    assert page.errors == []
    assert page.get_attribute("#s2", "aria-disabled") == "true"
    assert "your browser" in page.text_content(".lede") and "never leave this device" in page.text_content(".lede")


def test_without_the_model_it_says_so_plainly(page):
    page.click("#ours1")
    page.wait_for_function("document.getElementById('hint1').textContent.includes(\"couldn't start\")", timeout=10000)
    assert page.get_attribute("#s2", "aria-disabled") == "true"  # nothing claimed
    assert page.errors == []


def test_the_search_finds_the_things_squares_among_others(page):
    r = page.evaluate("""async () => {
      const E = await import('./eyes-core.js');
      let seed = 3; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647 - 0.5;
      const unit = (v) => { const n = Math.hypot(...v); return Float32Array.from(v, (x) => x / n); };
      const dim = 32, vec = () => unit(Array.from({ length: dim }, rnd));
      const mine = Array.from({ length: 16 }, vec), bg = vec();
      // your thing: a 6 by 6 crop, its edge the backdrop, its middle the thing
      const tsq = [];
      for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++)
        tsq.push(x === 0 || y === 0 || x === 5 || y === 5 ? unit(bg.map((v, k) => v + 0.1 * rnd())) : mine[(y * 6 + x) % 16]);
      const thing = { squares: tsq, gw: 6, gh: 6, dim };
      // a room of 20 by 14 squares, the thing's squares (a little changed) at columns 13 to 16, rows 4 to 7
      const sq = [];
      for (let y = 0; y < 14; y++) for (let x = 0; x < 20; x++)
        sq.push(x >= 13 && x <= 16 && y >= 4 && y <= 7 ? unit(mine[(y * 4 + x) % 16].map((v) => v + 0.15 * rnd())) : vec());
      const room = { squares: sq, gw: 20, gh: 14, dim, box: { x: 0, y: 0, w: 1400, h: 980 } };
      const map = E.likeness(thing, room), p = E.places(map, room, 3);
      const says = [{ whole: 0.9, colour: 0.9 }, { whole: 0.9, colour: 0.4 }, { whole: 0.7, colour: 0.9 }, { whole: 0.3, colour: 1 }].map(E.verdict);
      return { at: p[0].at, tries: p[0].tries.length, others: p.slice(1).map((q) => q.at), sure: E.SURE, maybe: E.MAYBE, says };
    }""")
    assert 13 * 70 <= r["at"]["x"] <= 17 * 70 and 4 * 70 <= r["at"]["y"] <= 8 * 70  # the thing's place, first
    assert r["tries"] >= 2 and all(not (13 * 70 <= o["x"] <= 17 * 70 and 4 * 70 <= o["y"] <= 8 * 70) for o in r["others"])
    assert 0 < r["maybe"] < r["sure"] < 1  # Andy asks between the two, says "found" above
    assert r["says"] == ["found", "maybe", "maybe", "none"]  # alike but another colour: asked, never "found"


def test_the_colour_fingerprint_tells_a_blue_thing_from_a_red_one(page):
    r = page.evaluate("""async () => {
      const E = await import('./eyes-core.js');
      const square = (r, g, b) => { const d = new Uint8ClampedArray(28 * 28 * 4); for (let i = 0; i < 28 * 28; i++) d.set([r, g, b, 255], 4 * i); return d; };
      const print = (rgb) => E.colourPrint(rgb, 28, [0, 1, 2, 3]);
      const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);
      const blue = print(square(40, 70, 200)), blue2 = print(square(50, 80, 190)), red = print(square(200, 50, 40)), white = print(square(235, 235, 230));
      return { same: dot(blue, blue2), other: dot(blue, red), grey: dot(blue, white), unit: dot(blue, blue) };
    }""")
    assert abs(r["unit"] - 1) < 1e-5 and r["same"] > 0.9 and r["other"] < 0.1 and r["grey"] < 0.1
