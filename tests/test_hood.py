import json
import urllib.request

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.hood import Hood, Timed
from heyandy_meta.screen.server import hood_json, serve
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_a_turn_is_timed_from_the_end_of_the_words_stage_by_stage():
    c = Clock()
    hood = Hood(clock=c)

    class Eyes:
        def find(self, frame, q):
            c.t += 0.4
            return []

    eyes = hood.wrap(Eyes(), {"find": ("see", "SAM 3.1")})
    hood.heard(99.0, 0.3)  # the words ended a second ago; hearing them took 0.3 s
    hood.sound()  # the "heard" note
    hood.begin()
    hood.kind("find")
    eyes.find(None, "keys")
    with hood.span("speak", "SeamlessM4T v2"):
        c.t += 1.5
    hood.end()
    latest = hood.snapshot()["latest"]
    assert latest["what"] == "a search" and latest["total"] == pytest.approx(2.9)
    assert latest["stages"] == {"hear": 0.3, "see": 0.4, "speak": 1.5} and latest["first_sound"] == pytest.approx(1.0)
    assert [s[0] for s in latest["spans"]] == ["hear", "see", "speak"] and latest["spans"][1][3] == "SAM 3.1"
    assert hood.since["see"] == 1 and hood.since["turns"] == 1


def test_listening_again_before_the_turn_joins_its_timeline():
    """November 2: a conversation's "heard" note came 2.2 s after the words on the robot and the timeline had a hole:
    listening again (told no language) is now in it."""
    c = Clock()
    hood = Hood(clock=c)
    hood.heard(99.0, 0.3)  # words ended at 99.0; heard by 99.3
    hood.heard_again(99.35, 99.6)
    c.t = 100.2
    hood.begin()
    hood.end()
    spans = hood.snapshot()["latest"]["spans"]
    assert ["hear", 0.0, 0.3, ""] in spans and ["hear", 0.35, 0.6, "again"] in spans
    assert hood.snapshot()["latest"]["stages"]["hear"] == pytest.approx(0.55)
    hood.begin()  # the next turn starts clean
    hood.end()
    assert [x for x in hood.snapshot()["latest"]["spans"] if x[3] == "again"] == []


def test_the_wrapper_passes_everything_else_straight_through():
    class Body:
        yaw = 0.0
        log = []

        def look(self, y, p):
            self.yaw = y

        def capture(self):
            return "frame"

    body = Body()
    timed = Timed(body, Hood(), {"look": ("move", "motors")})
    timed.look(12.0, 5.0)
    timed.yaw = 30.0  # set through it: the body's own
    assert body.yaw == 30.0 and timed.capture() == "frame" and timed.log is body.log
    body.capture = lambda: "patched"  # a test patching the body itself is seen through the wrapper
    assert timed.capture() == "patched"


def test_andys_own_turns_are_timed_with_its_models_names(tmp_path):
    a, _, _ = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.hear("where are my keys?")
    latest = a.hood.snapshot()["latest"]
    assert latest["kind"] == "find" and {"see", "move", "camera", "speak"} <= set(latest["stages"])
    models = {s[3] for s in latest["spans"]}
    assert "SAM 3.1" in models and "SeamlessM4T v2" in models


def test_show_me_under_the_hood_opens_the_page_on_the_tv(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "on the screen" in a.hear("Hey Andy, show me under the hood")
    assert a.screen.snapshot()["hood"] is True and a.screen.hood_left() > 60
    assert parse("how did you do that?").kind == "hood" and parse("show me how you work").kind == "setup"


def test_the_hood_page_and_its_numbers_are_served_and_hold_no_words(tmp_path):
    a, _, _ = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.hear("where are my keys?")
    server = serve(a.screen, port=0)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(base + "/hood") as r:
            assert b"Under the hood" in r.read()
        with urllib.request.urlopen(base + "/hood.json") as r:
            data = json.loads(r.read())
    finally:
        server.shutdown()
    assert data["latest"]["kind"] == "find" and data["sample"] is False
    assert "keys" not in json.dumps(data)  # numbers and models' names: never what was said


def test_the_public_demos_sample_was_recorded_on_the_robot_and_says_so():
    data = hood_json(ScreenState(), sample=True)
    assert data["sample"] is True and data["latest"]["what"] == "a search" and data["recorded"].startswith("2026-10-31")
    assert data["latest"]["stages"]["see"] > 0 and data["latest"]["first_sound"] is not None


def test_meta_live_shows_each_meta_model_while_it_works_then_how_long_it_took():
    c = Clock()
    hood = Hood(clock=c)
    seen = {}

    class Eyes:
        def find(self, frame, q):
            c.t += 0.3
            seen["during"] = hood.calls()  # what the TV shows while SAM 3.1 works
            c.t += 0.2
            return []

    class Body:
        def look(self, y, p):
            c.t += 1.0

    eyes = hood.wrap(Eyes(), {"find": ("see", "SAM 3.1")})
    body = hood.wrap(Body(), {"look": ("move", "the robot's motors")})
    hood.heard(c.t, 0.2)
    body.look(10, 0)  # the robot's own motors: not a Meta model, not on the strip
    eyes.find(None, "cup")
    live = seen["during"]["live"]
    assert live == [{"stage": "see", "model": "SAM 3.1", "where": "on this computer", "s": 0.3}]
    done = hood.calls()["done"]
    assert [d["model"] for d in done] == ["SAM 3.1", "Omnilingual ASR"] and done[0]["s"] == pytest.approx(0.5)
    c.t += 25
    assert hood.calls() == {"live": [], "done": []}  # 20 s of quiet: gone


def test_a_cloud_model_is_said_to_be_in_the_cloud():
    hood = Hood()
    with hood.span("think", "Muse Spark"):
        pass
    assert hood.calls()["done"][0]["where"] == "Meta Model API"


def test_the_tv_state_carries_the_strip(tmp_path):
    a, _, _ = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.hear("where are my keys?")
    calls = a.screen.snapshot()["calls"]
    assert any(d["model"] == "SAM 3.1" for d in calls["done"]) and all(d["stage"] != "move" for d in calls["done"])


def test_the_turn_plays_back_at_its_own_speed_with_each_model_lit_as_it_works(tmp_path):
    """November 2: the hood was a still chart a judge had to read. Now the turn plays back when the page opens (not with
    reduced motion): a playhead across the stages, each bar lit as its model works, the number counting up and the
    model at work named; "Watch it again" plays it once more. The chart is drawn once per turn, not every second."""
    import functools
    import http.server
    import shutil
    import threading
    from importlib.resources import files

    playwright = pytest.importorskip("playwright.sync_api")
    screen = files("heyandy_meta.screen")
    shutil.copy(screen.joinpath("hood.html"), tmp_path / "hood.html")
    sample = json.loads(screen.joinpath("hood_sample.json").read_text())
    (tmp_path / "hood.json").write_text(json.dumps({**sample, "sample": True}))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(tmp_path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/hood.html"
    try:
        with playwright.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:  # noqa: BLE001 - no browser here: skip
                pytest.skip(f"no Chromium for Playwright: {e}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_selector(".playhead", timeout=5000)  # it plays as the page opens
            # every model named as it works, recorded in the page as the words change (sampling from here, a slow
            # machine missed the short ones), with the turn played again forty times as fast
            page.evaluate("""() => { window.named = []; const d = document.getElementById('doing');
              new MutationObserver(() => window.named.push(d.textContent)).observe(d, { childList: true, subtree: true, characterData: true });
              window.hoodReplay(40); }""")
            page.wait_for_function("document.getElementById('status').textContent.startsWith('Done')", timeout=10000)
            seen = set(page.evaluate("window.named"))
            status = page.text_content("#status")
            first = page.query_selector(".seg")
            page.wait_for_timeout(2300)  # two polls of hood.json
            after = page.evaluate("""() => ({ head: !!document.querySelector('.playhead'), total: document.getElementById('total').textContent,
                                              button: document.getElementById('replay').textContent, lit: document.querySelectorAll('.seg.on').length })""")
            redrawn = not first.evaluate("e => e.isConnected")
            still = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
            still.goto(url)
            still.wait_for_selector(".seg", timeout=5000)
            still.wait_for_timeout(1500)
            autoplay_when_reduced = bool(still.query_selector(".playhead"))
            phone = browser.new_page(viewport={"width": 390, "height": 844})
            phone.goto(url)
            phone.wait_for_selector(".seg", timeout=5000)
            wide = phone.evaluate("document.documentElement.scrollWidth > innerWidth")
            browser.close()
    finally:
        server.shutdown()
    assert errors == [] and status == "Done: 12.8 seconds from the end of the words."
    assert any(s and s.startswith("Seeing") for s in seen) and any(s and s.startswith("Speaking") for s in seen)
    assert after == {"head": False, "total": "12.8s", "button": "▶ Watch it again, at its own speed", "lit": 0}
    assert not redrawn and not autoplay_when_reduced and not wide
