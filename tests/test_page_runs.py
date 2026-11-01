"""The TV page in a real browser: no script error, on Andy's own TV and in the public demo.

A name declared twice (2026-10-31, the public demo's ask box) stopped the whole script: the TV would have stayed blank
at the robot as well as in the demo, and no other test could see it. This one loads the page as a browser does.
Skipped where Playwright's Chromium isn't installed.
"""
import functools
import sys
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001 - no browser here: skip, as the docstring says
            pytest.skip(f"no Chromium for Playwright: {e}")
        yield b
        b.close()


def errors_on(browser, url: str, wait_ms: int = 1500, act=None) -> list[str]:
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # the page's own catch logs what stopped a render (a Chinese "：" did, Nov 1, with nothing thrown)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.goto(url)
    page.wait_for_timeout(wait_ms)
    if act:
        act(page)
    page.close()
    return errors


def test_andys_own_tv_runs_without_a_script_error(browser):
    state = ScreenState()
    state.said("There it is!", "device")
    server = serve(state, port=0)
    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/") == []
    finally:
        server.shutdown()


def test_the_public_demo_runs_and_asking_andy_plays_a_scene(browser):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    url = f"http://127.0.0.1:{server.server_address[1]}/?ask=I%27m%20ringing%20my%20phone"
    seen = {}

    def check(page):
        seen.update(page.evaluate("() => ({chosen, kicker: document.getElementById('kicker').textContent,"
                                  " routes: ['help me reach it', 'where are my keys', 'show me the room'].map(route)})"))

    try:
        assert errors_on(browser, url, 2500, check) == []
        assert seen["chosen"] == "sound" and seen["kicker"] == "Listening for your phone"
        assert seen["routes"] == ["guide", "find", "room"]
    finally:
        server.shutdown()


def test_the_settings_gear_opens_its_menu_and_under_the_hood_runs(browser):
    from heyandy_meta.screen.hood import Hood

    state = ScreenState()
    state.hood = Hood()
    server = serve(state, port=0)
    seen = {}

    def gear(page):
        page.click("#gear")
        seen["menu"] = page.evaluate("() => !document.getElementById('menu').hidden")
        page.click("#m-hood")
        page.wait_for_timeout(1500)
        seen["url"], seen["title"] = page.url, page.evaluate("() => document.querySelector('h1').textContent")

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/", 1200, gear) == []
        assert seen["menu"] and seen["url"].endswith("/hood") and seen["title"] == "Under the hood"
    finally:
        server.shutdown()


def test_every_demo_scene_draws_in_full(browser):
    """Each scene of the public demo, alone: the page draws it with no error, and the found scenes show their picture
    (the Mandarin scene once stopped at the list of things, and the TV stayed half empty)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import IN_LANGUAGE, SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    every = (*SCENES, *IN_LANGUAGE)
    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in every}, listed=list(SCENES))
    shown = {}
    try:
        for name in every:
            def look(page, name=name):
                shown[name] = page.evaluate("() => document.querySelectorAll('#card img, #card canvas, #card svg').length")
            url = f"http://127.0.0.1:{server.server_address[1]}/?scene={name}"
            assert errors_on(browser, url, 1200, look) == [], name
        assert shown["mandarin"] and shown["spanish"] and shown["found"] and all(shown[n] for n in IN_LANGUAGE)
    finally:
        server.shutdown()


def test_asking_andy_in_any_of_its_languages_plays_that_languages_scene(browser):
    """Typed in one of Andy's fifteen languages, Ask Andy plays the find in it, as Andy notices the language it's
    called in; the page's everyday words are the same lists Andy's ears use (companion/language.py)."""
    import json
    import re

    from heyandy_meta.companion.language import EVERYDAY
    from heyandy_meta.screen.server import page

    lists = json.loads(re.search(r"const EVERYDAY = (\{.*?\});", page()).group(1))
    assert lists == EVERYDAY
    server = serve(ScreenState(), port=0)
    asked = ["我的眼镜在哪里？", "¿Dónde están mis gafas?", "Где мои очки?", "Де мої окуляри?", "내 안경 어디 있어?",
             "Où sont mes lunettes ?", "Wo ist meine Brille?", "Kính của tôi đâu rồi?", "मेरा चश्मा कहाँ है?", "أين نظارتي؟",
             "Nasaan ang salamin ko?", "Onde estão meus óculos?", "Dove sono i miei occhiali?", "Gdzie są moje okulary?",
             "Where are my keys?", "help me reach it"]
    got = {}

    def routes(page_):
        got["r"] = page_.evaluate("(qs) => qs.map(route)", asked)

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/", 1200, routes) == []
    finally:
        server.shutdown()
    assert got["r"] == ["mandarin", "spanish", "in-ru", "in-uk", "in-ko", "in-fr", "in-de", "in-vi", "in-hi", "in-ar",
                        "in-tl", "in-pt", "in-it", "in-pl", "find", "guide"]


def test_say_it_has_a_microphone_scores_phrases_by_ctc_and_snaps_near_misses(browser):
    """The demo's 🎙 (Meta's wav2vec 2.0 in the browser; evals/say_it.py measures it with the model): the phrase that
    explains the letters best wins, by the CTC forward algorithm; a word one letter off a word Andy's routes know is
    that word. No network here: the model isn't fetched, the maths is checked on made-up letter likelihoods."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    got = {}

    def check(page):
        got.update(page.evaluate("""() => {
          const V = 32, frames = (word) => [...word].flatMap((c) => {  // each letter likely for two frames, then a blank
            const row = (i) => { const r = new Float32Array(V).fill(Math.log(0.01)); r[i] = Math.log(0.69); return r; };
            return [row(LETTER[c]), row(LETTER[c]), row(0)];
          });
          const lp = frames("HI");
          return { mics: document.querySelectorAll('button.mic').length, hi: ctc(lp, letters('hi')), ho: ctc(lp, letters('ho')),
                   room: snap('show me the rom'), pass: snap('wheres my pasport'), typed: route(snap('what time is it')) };
        }"""))

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/?explore", 1500, check) == []
    finally:
        server.shutdown()
    assert got["mics"] >= 1 and got["hi"] < got["ho"]
    assert got["room"] == "show me the room" and "passport" in got["pass"]


def test_the_story_opens_on_the_robot_when_the_space_has_a_clip(browser):
    """build_static_space.py --clip: the robot itself, filmed, is the story's first chapter, over the TV, and gone after
    it; with no clip, the story is as it was."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    seen = {}
    try:
        for with_clip in (True, False):
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            if with_clip:
                page.add_init_script("window.HEYANDY_CLIP = 'robot.mp4'; window.HEYANDY_CLIP_SECONDS = 6;")
            page.goto(url)
            page.wait_for_function("document.body.classList.contains('storying')", timeout=10000)
            seen[with_clip] = page.evaluate("""() => { const first = [STORY.length, STORY[0][2], !!document.getElementById('clip')];
                                                      go(1); return [...first, !!document.getElementById('clip')]; }""")
            page.close()
    finally:
        server.shutdown()
    assert seen[True][1:] == ["Andy, on the table", True, False] and seen[True][0] == seen[False][0] + 1
    assert seen[False][2] is False and seen[False][1] == "Meet Andy"
