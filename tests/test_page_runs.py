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
