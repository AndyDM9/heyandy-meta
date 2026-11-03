"""Andy's language from the TV's settings (screen/server.py POST /language, page.html's list): the one thing the TV
can change, and only from its own page. November 2: the founder asked how the language is changed, and whether it's
part of the settings; by voice it was, and now from the TV too, with a remote or a mouse."""
import http.client
import json
import threading

import pytest

from heyandy_meta.companion.language import LANGUAGES
from heyandy_meta.screen.server import page, serve
from heyandy_meta.screen.state import ScreenState


def tv(on_language=None):
    server = serve(ScreenState(), port=0, on_language=on_language, languages=tuple(LANGUAGES))
    return server, server.server_address[1]


def key_of(port) -> str:
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
    html = c.getresponse().read().decode()
    return html.split('<meta name="andy-settings" content="', 1)[1].split('"', 1)[0]


def post(port, body, host=None, origin="same", kind="application/json"):
    host = host or f"127.0.0.1:{port}"
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    headers = {"Host": host, "Content-Type": kind, "Content-Length": str(len(data))}
    if origin:
        headers["Origin"] = f"http://{host}" if origin == "same" else origin
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("POST", "/language", body=data, headers=headers)
    return c.getresponse().status


def test_only_the_tvs_own_page_can_change_the_language():
    asked, done = [], threading.Event()
    server, port = tv(lambda to: (asked.append(to), done.set()))
    try:
        key = key_of(port)
        assert len(key) >= 24
        assert post(port, {"to": "ko", "token": key}, host="andy.example:80") == 421  # a rebound name
        assert post(port, {"to": "ko", "token": key}, origin="https://evil.example") == 403  # another site's page
        assert post(port, {"to": "ko", "token": key}, origin=None) == 403
        assert post(port, b"to=ko", kind="application/x-www-form-urlencoded") == 415  # a plain form from elsewhere
        assert post(port, {"to": "ko", "token": "guessed"}) == 403
        assert post(port, {"to": "xx", "token": key}) == 400  # not one of Andy's
        assert post(port, b"{" * 600) == 413
        assert asked == []
        assert post(port, {"to": "ko", "token": key}) == 202
        assert done.wait(2) and asked == ["ko"]
    finally:
        server.shutdown()


def test_a_tv_with_no_language_setting_changes_nothing_and_the_demo_has_no_key():
    server, port = tv(None)
    try:
        assert key_of(port) == ""
        assert post(port, {"to": "ko", "token": ""}) == 404
    finally:
        server.shutdown()
    assert '<meta name="andy-settings" content="">' in page()  # the public demo's page (the Space's build): no key


def test_andy_switches_and_says_so_as_when_asked_by_voice(tmp_path):
    from tests.test_app import andy

    a, body, _ = andy(tmp_path=tmp_path)
    switched = []
    a.set_language = lambda to: switched.append(to) or "Okay, I'll speak Korean now."
    a.language_from_tv("ko")
    assert switched == ["ko"] and [e[1] for e in body.log if e[0] == "say"][-1] == "Okay, I'll speak Korean now."


def test_the_settings_list_on_andys_tv_switches_it(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    asked, done = [], threading.Event()
    server, port = tv(lambda to: (asked.append(to), done.set()))
    try:
        with playwright.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:  # noqa: BLE001 - no browser here: skip
                pytest.skip(f"no Chromium for Playwright: {e}")
            pg = browser.new_page(viewport={"width": 1920, "height": 1080})
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(f"http://127.0.0.1:{port}/")
            pg.click("#gear")
            assert pg.is_visible("#m-langs") and "or choose it here" in pg.text_content("#m-lang")
            pg.click("#m-langs")
            names = pg.eval_on_selector_all("#m-langlist button", "els => els.map(e => e.textContent)")
            pg.click("#m-langlist button[lang=ko]")
            assert done.wait(3) and asked == ["ko"]
            pg.wait_for_selector("#menu", state="hidden", timeout=3000)  # closed once the TV has asked
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
    assert len(names) == 15 and "한국어" in names and "English" in names
