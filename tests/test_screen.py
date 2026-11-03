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


def test_the_public_demo_gives_each_visitor_their_own_scene():
    import json as _json

    calls = []
    srv = serve(ScreenState(), port=0, scenes={"found": lambda: calls.append("found") or {"caption": "found it"},
                                                "idle": lambda: {"caption": ""}})
    try:
        url = f"http://127.0.0.1:{srv.server_port}/state.json"
        a = _json.load(urllib.request.urlopen(url + "?scene=found"))
        assert a["caption"] == "found it" and a["demo"] == ["found", "idle"] and calls == ["found"]
        b = _json.load(urllib.request.urlopen(url + "?scene=nonsense"))  # anything else: the shared, read-only state
        assert b["demo"] == ["found", "idle"] and "caption" in b
    finally:
        srv.shutdown()


def test_the_tv_answers_only_to_its_own_name():
    import urllib.error

    srv = serve(ScreenState(), port=0)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert urllib.request.urlopen(url + "/state.json").status == 200
        with pytest.raises(urllib.error.HTTPError) as e:  # a page that tricked a browser into another name for it
            urllib.request.urlopen(urllib.request.Request(url + "/state.json", headers={"Host": "andy.localhost:8765"}))
        assert e.value.code == 421
    finally:
        srv.shutdown()


def test_the_live_view_shows_only_while_a_search_runs_and_goes_when_it_ends():
    from heyandy_meta.finder.search import Found
    from heyandy_meta.models.common import Mask
    from heyandy_meta.robot.body import Frame

    s = ScreenState()
    frame, mask = Frame(b"\xff\xd8jpeg", 1920, 1080, 0.0, 10.0), Mask("mug", (900, 500, 1000, 600), 0.9)
    s.glimpse(frame, [mask])
    assert "glimpse" not in s.snapshot()  # no search running: nothing shown
    s.looking("mug")
    s.timer_start()
    s.glimpse(frame, [mask])
    g = s.snapshot()["glimpse"]
    assert g["src"].startswith("data:image/jpeg;base64,") and g["masks"][0]["box"] == [900, 500, 1000, 600]
    s.glimpse(Frame(b"", 1920, 1080, 0.0, 0.0), [])  # the pretend room: no camera, nothing replaces it
    assert s.snapshot()["glimpse"]["v"] == g["v"]
    s.found(Found("mug", 0.0, 10.0, 0.9, frame, mask, 2), "There it is!")
    assert "glimpse" not in s.snapshot()  # the search is over: the live view is gone


@pytest.mark.parametrize("next_card", ["remember", "help", "answer", "looking"])
def test_the_room_in_3d_gives_way_to_what_is_shown_next(next_card):
    from heyandy_meta.screen.state import ScreenState

    s = ScreenState()
    s.room(b"\x00\x00" * 3, [{"label": "keys", "point": [0.1, 0.2, 0.5], "metres": 0.55}])
    assert s.snapshot()["room"] is not None
    {"remember": lambda: s.remember_list(["keys: just now"]), "help": s.show_help,
     "answer": lambda: s.answered("It's sunny.", []), "looking": lambda: s.looking("keys")}[next_card]()
    assert s.snapshot()["room"] is None


def test_every_demo_scene_has_a_name_in_the_scene_bar():
    import re
    import sys
    from importlib.resources import files
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    names = re.search(r"const NAMES = \{(.*?)\};", page, re.S).group(1)
    assert set(SCENES) <= set(re.findall(r"(\w+):", names))


def test_the_reveal_plays_only_for_a_find_made_just_now():
    """The TV's Reveal (page.html) runs when a find's picture has at least 112 of its 120 s left: a reload of an older
    card, or the cup game, never replays it."""
    from importlib.resources import files

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    assert "function reveal(" in page
    assert "if (!s.game && !s.picture.trails && s.picture.seconds_left >= 112 && shot !== revealedShot)" in page
    assert "revealedShot = shot; reveal(s.picture, s.seconds);" in page  # once per find, not again when its aim is checked
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import show

    from heyandy_meta.screen.state import ScreenState

    s = ScreenState()
    show(s, "found")
    assert s.snapshot()["picture"]["seconds_left"] >= 112


def test_the_story_opens_only_the_public_demo():
    """Story mode starts when the page sees demo scenes (the Space, scripts/demo_screen.py), never on Andy's own TV,
    and not when a link names a scene (?scene=...), asks to explore (?explore) or asks Andy something (?ask=...)."""
    from importlib.resources import files

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    assert 'if (s.demo && !scenes) {' in page
    assert 'else if (!chosen && !q.has("explore") && scenes.includes("room")) {' in page
    assert 'if (q.has("story")) startStory(); else welcome();' in page  # the front door first, or the story when asked
    assert 'if (q.get("ask")) ask(q.get("ask"));' in page  # a link that asks plays that scene instead
    import re

    story = re.search(r"const STORY = \[(.*?)\n  \];", page, re.S).group(1)
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES

    assert set(re.findall(r'\["(\w+)", \d+,', story)) <= set(SCENES)  # every chapter is a real scene


def test_the_tvs_face_gets_the_persons_direction_only_and_only_while_fresh():
    from heyandy_meta.screen.state import ScreenState

    t = [100.0]
    s = ScreenState(clock=lambda: t[0])
    assert "gaze" not in s.snapshot()
    s.gaze_at(32.4, 8.1)
    assert s.snapshot()["gaze"] == {"yaw": 32.4, "pitch": 8.1, "age": 0.0}  # a direction, never a picture
    t[0] += 31
    assert "gaze" not in s.snapshot()  # an old sighting isn't a person still there


def test_the_tv_fits_any_window_and_nothing_covers_the_captions():
    """A browser window with its toolbars is wider than 16:9 (1920x960): sized by width alone, the cards grew past
    their row and slid over Andy's captions (the founder's screenshot, 2026-10-31). The height decides there now."""
    from importlib.resources import files

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    assert "html { font-size: min(calc(100vw / 120), calc(100vh / 67.5)); }" in page
    assert "main > * { min-height: 0; }" in page and "#captions { position: relative; z-index: 1;" in page


def test_a_tall_or_narrow_screen_gets_one_readable_column():
    """Everybody's screen is different (the founder, 2026-10-31): a phone, an upright tablet or a narrow window gets
    one column with the card first, type sized for that screen, a page that scrolls and captions that stay in view;
    and the Reveal's push-in never slides the photo far enough to show its edge."""
    from importlib.resources import files

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    tall = page.split("@media (max-aspect-ratio: 6/5), (max-width: 900px) {", 1)[1].split("\n  }\n", 1)[0]
    assert "html { font-size: min(calc(100vw / 34), 18px); }" in tall
    assert "main { grid-template-columns: 1fr;" in tall and "main > #card { order: -1;" in tall
    assert "body { height: auto; min-height: 100vh; overflow-y: auto; }" in tall
    assert "#captions { position: sticky; bottom: 0.8rem;" in tall
    assert "body.storying .stage { transform: none; height" not in page  # the story's TV is the tall layout, not a 16:9 miniature
    assert "overflow: visible; transform-origin: var(--ox) var(--oy);" in page
    assert "const tx = keep(W * 0.68 - ox," in page and "const ty = keep(H * 0.36 - oy," in page


def test_a_card_with_more_than_its_room_shrinks_together_and_pictures_give_way_first():
    """The founder's browser cut off the last model names on the welcome card (2026-10-31): a card that holds more
    than its room now shrinks all together, never below 0.6, instead of losing its bottom; a picture beside its facts
    takes only the height that's left, so words don't shrink for it."""
    from importlib.resources import files

    page = files("heyandy_meta.screen").joinpath("page.html").read_text()
    assert "function fitAll()" in page and "fit(card, [$(\"body\")]); fit(side, []);" in page and "let lo = 0.6, hi = 1;" in page
    assert "    fitAll();\n    ambient(s);" in page  # after every render; it only works when what's shown changes
    assert ".split > figure svg { height: 100%; width: auto; max-width: 100%; }" in page
    assert "#help { position: fixed; top: 0; right: 0; bottom: 0; left: 0; display: flex;" in page and "overflow-y: auto;" in page  # the help scrolls
