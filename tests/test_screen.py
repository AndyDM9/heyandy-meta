import json
import urllib.error
import urllib.request

import pytest

from heyandy_meta.finder.search import Found
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.body import Frame
from heyandy_meta.screen.server import COLORS, page, serve
from heyandy_meta.screen.state import PICTURE_SECONDS, ScreenState


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def found():
    mask = Mask("glasses", (100, 200, 160, 230), 0.9, (130.0, 215.0), 900, outline="M0 0L60 0L60 30Z", outline_scale=(1.0, 1.0))
    return Found("glasses", 30.0, 20.0, 0.9, Frame(b"\xff\xd8jpeg", 1920, 1080, 30.0, 20.0), mask, looks=5)


def test_the_picture_is_shown_then_dropped_after_two_minutes():
    clock = Clock()
    s = ScreenState(clock)
    s.found(found(), "On the table, to my left")
    pic = s.snapshot()["picture"]
    assert pic["src"].startswith("data:image/jpeg;base64,") and pic["outline"].startswith("M")
    assert pic["box"] == [100, 200, 160, 230] and pic["words"] == "On the table, to my left"
    clock.t += PICTURE_SECONDS
    assert s.snapshot()["picture"] is None
    assert s._picture is None  # gone from memory, not just hidden


def test_caption_and_who_answered():
    s = ScreenState()
    s.said("It's half past ten.", source="device", reason="everyday turn")
    snap = s.snapshot()
    assert (snap["caption"], snap["source"], snap["reason"]) == ("It's half past ten.", "device", "everyday turn")


def _luminance(hex_):
    def ch(c):
        c = int(hex_[c:c + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(1) + 0.7152 * ch(3) + 0.0722 * ch(5)


@pytest.mark.parametrize("name", ["text", "muted", "accent", "cloud"])
def test_every_text_colour_is_at_least_7_to_1(name):
    a, b = _luminance(COLORS[name]), _luminance(COLORS["bg"])
    assert (max(a, b) + 0.05) / (min(a, b) + 0.05) >= 7.0


def test_page_has_no_unfilled_colours():
    assert "{{" not in page()


def test_served_on_this_computer_only_and_read_only():
    s = ScreenState()
    s.said("Hello", source="device")
    server = serve(s, port=0)
    try:
        host, port = server.server_address
        assert host == "127.0.0.1"
        base = f"http://127.0.0.1:{port}"
        assert b"Andy, a robot" in urllib.request.urlopen(base + "/").read()
        assert json.loads(urllib.request.urlopen(base + "/state.json").read())["caption"] == "Hello"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(base + "/state.json", data=b"{}", method="POST"))
    finally:
        server.shutdown()


def test_timer_plan_memory_and_sources():
    clock = Clock()
    s = ScreenState(clock)
    s.timer_start()
    s.step("look: right, far right")
    clock.t += 2.4
    s.step("look closer: place 1")
    snap = s.snapshot()
    assert snap["running"] and snap["seconds"] == 2.4 and snap["steps"] == ["look: right, far right", "look closer: place 1"]
    clock.t += 1.0
    s.timer_stop()
    clock.t += 5.0
    assert s.snapshot()["seconds"] == 3.4 and not s.snapshot()["running"]
    s.remember_list(["keys: to my right, 12 minutes ago"])
    s.answered("Open Saturday.", [("Market hours", "https://www.townmarket.org/hours")])
    snap = s.snapshot()
    assert snap["memory"] == ["keys: to my right, 12 minutes ago"]
    assert snap["sources"] == [{"title": "Market hours", "url": "https://www.townmarket.org/hours"}]
    s.clear()
    assert s.snapshot()["steps"] == [] and s.snapshot()["seconds"] is None
