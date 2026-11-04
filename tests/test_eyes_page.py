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
def pw():
    with playwright.sync_playwright() as p:  # one Playwright per module
        yield p


@pytest.fixture(scope="module")
def page(site, pw):
    try:
        browser = pw.chromium.launch()
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
    assert page.is_hidden("#phone")  # the code to carry it to a phone: only over https (or ?qr), and only if it loads


def test_without_the_model_it_says_so_plainly(page):
    page.click("#ours1")
    page.wait_for_function("document.getElementById('hint1').textContent.includes(\"couldn't\")", timeout=10000)
    said = page.evaluate("document.getElementById('hint1').textContent")
    assert "couldn't download" in said and "connection" in said  # a failed download, said as one (not "your browser")
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


def test_sweeping_the_room_waits_for_your_thing_and_looks_at_one_place_a_frame(page):
    assert "Sweep the room, live" in page.text_content("#sweep")
    assert page.get_attribute("#s2", "aria-disabled") == "true"  # step 2 can't be pressed before your thing is known
    page.eval_on_selector("#sweep", "b => b.click()")  # and pressed anyway, by script: no camera, nothing claimed
    assert "First, show Andy your thing" in page.text_content("#stage2") and page.errors == []
    one = page.evaluate("""async () => {
      const E = await import('./eyes-core.js');
      const unit = (v) => { const n = Math.hypot(...v); return Float32Array.from(v, (x) => x / n); };
      const sq = Array.from({ length: 12 * 8 }, (_, i) => unit([Math.sin(i), Math.cos(i * 1.3), 0.5, (i % 7) / 7]));
      const room = { squares: sq, gw: 12, gh: 8, dim: 4, box: { x: 0, y: 0, w: 640, h: 360 } };
      const thing = { squares: sq.slice(0, 16), gw: 4, gh: 4, dim: 4 };
      return E.places(E.likeness(thing, room), room, 1).length;
    }""")
    assert one == 1  # live, each frame looks again at only its best place (evals/eyes_live.py measures the whole sweep)


def test_the_library_comes_from_this_sites_own_copy_when_the_cdn_cant_be_reached(page, tmp_path):
    """November 2: the demo's libraries came only from jsDelivr, so a CDN that's down or blocked on a judge's network
    would have stopped Andy's eyes and "Say it". Now eyes-core.js's library() tries the CDN, then vendor/ (the Space's
    build copies it there, checked by SHA-256), and points the runtime's files at vendor/ too."""
    import shutil

    shutil.copy(files("heyandy_meta.screen").joinpath("eyes-core.js"), tmp_path / "eyes-core.js")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "transformers.min.js").write_text(
        'export const env = {backends: {onnx: {wasm: {}}}}; export const from = "vendor";')
    (tmp_path / "index.html").write_text("<!doctype html><title>t</title>")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        pg = page.context.browser.new_page()  # the module's browser: one Playwright per module
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(site) else r.continue_())  # no CDN
        pg.goto(f"{site}/index.html")
        got = pg.evaluate("import('./eyes-core.js').then(m => m.library()).then(T => [T.from, T.env.backends.onnx.wasm.wasmPaths])")
        pg.close()
    finally:
        server.shutdown()
    assert got == ["vendor", f"{site}/vendor/"]


def test_the_models_are_pinned_to_a_commit_not_main():
    core = files("heyandy_meta.screen").joinpath("eyes-core.js").read_text()
    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    assert 'REVISION = "ec7abea1a8757ec4f9f7b26399d31234ffaa6e6a"' in core and core.count("revision: REVISION") == 3
    assert 'revision: "a19f851b3d42865797e410752b4c570c871e4825"' in page


def guided_page(pw, site, camera: bool):
    """The page opened at ?find (the front door's "Find something of yours"), on a phone, with no network (so no model);
    with Chromium's fake camera when asked."""
    args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] if camera else []
    try:
        browser = pw.chromium.launch(args=args)
    except Exception as e:  # noqa: BLE001 - no browser here: skip
        pytest.skip(f"no Chromium for Playwright: {e}")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              permissions=["camera"] if camera else [])
    pg = ctx.new_page()
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(site) else r.continue_())
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(f"{site}/eyes.html?find")
    pg.wait_for_function("window.EYES_READY === true", timeout=10000)
    return browser, pg


def test_find_mode_opens_the_camera_full_screen_with_the_shutter_under_a_thumb(site, pw):
    """November 2: the front door's one action leads here, and on a phone the page was a long document of panels and
    six buttons, the live sweep below the fold. ?find is the same two steps, each the whole screen: a viewfinder with a
    frame to fill and a shutter at the bottom, then the sweep; the page's own steps underneath, unchanged."""
    browser, pg = guided_page(pw, site, camera=True)
    try:
        pg.wait_for_selector("#stage1 video", timeout=10000)
        pg.wait_for_selector("#stage1 .frame:not([hidden])", timeout=5000)
        shot = pg.evaluate("""() => { const b = document.querySelector('#stage1 .cam button.main').getBoundingClientRect();
          const v = document.querySelector('#stage1 video').getBoundingClientRect();
          return { guided: document.body.classList.contains('guided'), title: document.getElementById('guideTitle').textContent,
                   shutter: [b.width, b.height, b.bottom], fills: v.width >= innerWidth - 1 && v.height >= innerHeight - 1,
                   label: document.querySelector('#stage1 .cam button.main').getAttribute('aria-label'),
                   focused: document.activeElement === document.querySelector('#stage1 .cam button.main'),
                   chips: [...document.querySelectorAll('#guideChips button')].map(b => b.textContent),
                   wide: document.documentElement.scrollWidth > innerWidth } }""")
        assert shot["guided"] and shot["title"] == "Show me your thing" and shot["fills"] and not shot["wide"]
        assert shot["shutter"][0] >= 64 and shot["shutter"][2] >= 844 - 140  # big, and near the bottom: under a thumb
        assert shot["label"] == "Take the picture" and shot["focused"] and "keys" in shot["chips"]
        pg.click("#guideChips button:text('keys')")
        pg.click("#stage1 .cam button.main")  # no network, so no model: it says so, plainly, back on the page
        pg.wait_for_function("!document.body.classList.contains('guided')", timeout=15000)
        assert "couldn't download" in pg.text_content("#hint1") and pg.get_attribute("#s2", "aria-disabled") == "true"
        assert pg.evaluate("document.getElementById('thing').value") == "keys"
        assert pg.errors == []
    finally:
        browser.close()


def test_find_mode_without_a_camera_goes_back_to_the_page_and_says_what_to_do(site, pw):
    browser, pg = guided_page(pw, site, camera=False)
    try:
        pg.wait_for_function("!document.body.classList.contains('guided')", timeout=10000)
        assert "No camera here" in pg.text_content("#hint1") and pg.errors == []
    finally:
        browser.close()


def test_found_offers_the_link_to_share_never_the_photo(site, pw):
    browser, pg = guided_page(pw, site, camera=True)
    try:
        pg.wait_for_selector("#stage1 video", timeout=10000)
        pg.evaluate("document.getElementById('thing').value = 'mug'; navigator.share = undefined;"
                    "navigator.clipboard.writeText = async (t) => { window.copied = t; }; window.eyesGuide.found()")
        assert pg.text_content("#guideTitle") == "Found: your mug"
        buttons = pg.eval_on_selector_all("#guideDone > *", "els => els.map(e => e.textContent)")
        assert buttons == ["Share it", "Find something else", "See the robot"]
        pg.click("#guideDone button:text('Share it')")
        pg.wait_for_function("window.copied", timeout=3000)
        copied = pg.evaluate("window.copied")
        assert "found my mug" in copied and copied.endswith("/eyes.html?find") and "data:" not in copied
        assert pg.text_content("#guideDone button.main") == "Link copied"
        pg.keyboard.press("Escape")
        assert not pg.evaluate("document.body.classList.contains('guided')") and pg.errors == []
    finally:
        browser.close()


def test_a_find_shares_a_card_of_its_numbers_never_the_photo(site, pw):
    """Posts with a picture travel further than a link: a find now shares a card (1200 by 675) drawn from its own
    numbers (how alike, the colour, the seconds), with the link and a line. Never the photo: the card is drawn, not
    taken from the camera. Where a browser can't share files (a computer), the link is copied and the card saved."""
    browser, pg = guided_page(pw, site, camera=True)
    try:
        pg.wait_for_selector("#stage1 video", timeout=10000)
        pg.evaluate("""() => { document.getElementById('thing').value = 'mug';
          navigator.canShare = (d) => !!(d && d.files); navigator.share = async (d) => { window.shared = d; };
          window.eyesGuide.found({ whole: 0.86, colour: 0.98, box: { x: 0, y: 0, w: 10, h: 10 } }); }""")
        pg.click("#guideDone button:text('Share it')")
        pg.wait_for_function("window.shared", timeout=5000)
        got = pg.evaluate("""async () => { const f = window.shared.files[0], bmp = await createImageBitmap(f);
          return [window.shared.files.length, f.type, f.name, bmp.width, bmp.height, window.shared.url, window.shared.text] }""")
        pg.evaluate("""() => { navigator.canShare = undefined; navigator.share = undefined; window.shared = null;
          navigator.clipboard.writeText = async (t) => { window.copied = t; }; window.eyesGuide.found({ whole: 0.86, colour: 0.98 }); }""")
        pg.click("#guideDone button:text('Share it')")
        pg.wait_for_selector("#guideDone a.save", timeout=5000)
        saved = pg.evaluate("[document.querySelector('#guideDone a.save').download, !!window.copied]")
        assert pg.errors == []
    finally:
        browser.close()
    assert got[:5] == [1, "image/png", "andy-found-my-mug.png", 1200, 675]
    assert got[5].endswith("/eyes.html?find") and "found my mug" in got[6]
    assert saved == ["andy-found-my-mug.png", True]


def test_find_mode_speaks_in_andys_own_voice_in_the_visitors_language(site, pw):
    """Andy's eyes in find mode, voiced as the robot is: "Let me see." at the shutter, "Let me look around the room." as
    the sweep starts, "There it is!" (or "There they are!" for a pair) at the find, by hand in the language chosen on the
    front door (else the browser's), the words shown as they're said; the sound button silences it too."""
    silent = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
    voice = {code: {m: {"text": f"{code}:{m}", "file": silent + f"#{code}-{m}"} for m in ("see", "look", "it", "they")}
             for code in ("en", "ko")}
    try:
        browser = pw.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
    except Exception as e:  # noqa: BLE001 - no browser here: skip
        pytest.skip(f"no Chromium for Playwright: {e}")
    try:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, permissions=["camera"], locale="en-US")
        pg = ctx.new_page()
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(site) else r.continue_())
        import json

        pg.add_init_script(f"""window.EYES_VOICE = {json.dumps(voice)}; localStorage.setItem('andy-lang', 'ko');
          window.said = []; const A = window.Audio; window.Audio = function (src) {{ window.said.push(String(src).split('#')[1]); return new A(src); }};""")
        pg.goto(f"{site}/eyes.html?find")
        pg.wait_for_function("window.EYES_READY === true", timeout=10000)
        pg.wait_for_selector("#stage1 video", timeout=10000)
        lang = pg.evaluate("window.eyesGuide.lang()")
        pg.evaluate("document.getElementById('thing').value = 'keys'; window.eyesGuide.says('see'); window.eyesGuide.says('they')")
        caption = [pg.text_content("#guideSays"), pg.get_attribute("#guideSays", "lang"), pg.is_visible("#guideSays")]
        pg.evaluate("window.eyesGuide.hush(); window.eyesGuide.says('it')")
        said = pg.evaluate("window.said")
        ctx.close()
    finally:
        browser.close()
    assert lang == "ko" and said == ["ko-see", "ko-they"]  # Korean, chosen on the front door; nothing once hushed
    assert caption == ["ko:they", "ko", True]
