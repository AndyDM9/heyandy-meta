import json
import urllib.error
import urllib.request

import pytest

from heyandy_meta.finder.search import Found
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.body import Frame
from heyandy_meta.screen.server import THEMES, page, serve
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


def _rgb(hex_):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), (int(h[6:8], 16) / 255 if len(h) == 8 else 1.0)


def _luminance(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def _ratio(a, b):
    x, y = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


def _backgrounds(part):
    if part == "night":
        return [THEMES["night"][k] for k in ("bg1", "bg2", "bg3")]
    return [c for p in ("day", "morning", "evening") for k, c in THEMES[p].items() if k.startswith("bg")]


@pytest.mark.parametrize("part", ["day", "night"])
@pytest.mark.parametrize("name", ["ink", "muted", "accent", "cloud"])
def test_every_text_colour_is_at_least_7_to_1_on_a_frosted_panel_over_any_background(part, name):
    panel, alpha = _rgb(THEMES[part]["panel"])
    for bg in _backgrounds(part):
        seen = tuple(round(alpha * p + (1 - alpha) * b) for p, b in zip(panel, _rgb(bg)[0]))
        assert _ratio(_rgb(THEMES[part][name])[0], seen) >= 7.0, (part, name, bg)


@pytest.mark.parametrize("part", ["day", "night"])
def test_captions_are_at_least_7_to_1(part):
    assert _ratio(_rgb(THEMES[part]["caption"])[0], _rgb(THEMES[part]["caption_bg"])[0]) >= 7.0


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
        assert b"Pictures and voice stay on this computer" in urllib.request.urlopen(base + "/").read()
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


def test_the_typeface_is_served_by_andy_itself():
    srv = serve(ScreenState(), port=0)
    try:
        url = f"http://127.0.0.1:{srv.server_port}"
        data = urllib.request.urlopen(url + "/fonts/AtkinsonHyperlegibleNext.ttf").read()
        assert data[:4] == b"\x00\x01\x00\x00"  # a TrueType font
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(url + "/fonts/../server.py")
        assert "fonts.googleapis" not in page() and "http" not in page().split("<script>")[0].replace("http://www.w3.org", "")
    finally:
        srv.shutdown()
