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
