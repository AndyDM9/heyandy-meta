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
