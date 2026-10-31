import json
import threading
import urllib.error
import urllib.request

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.screen.remote import TRIES, Pairing, phone_state, serve_remote
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy


def test_a_code_pairs_one_phone_once_and_only_its_fingerprint_is_kept(tmp_path):
    t = [1000.0]
    p = Pairing(tmp_path / "remote.json", clock=lambda: t[0])
    code = p.new_code()
    assert len(code) == 6 and code.isdigit()
    key = p.pair(code)
    assert key and p.knows(key) and p.pair(code) is None  # one phone per code
    assert key not in (tmp_path / "remote.json").read_text()  # only its SHA-256 is written down
    assert Pairing(tmp_path / "remote.json").knows(key)  # and it survives a restart
    assert not p.knows("a guess") and not p.knows(None)
    assert p.forget_all() == 1 and not p.knows(key)


def test_codes_run_out_with_time_and_with_wrong_tries(tmp_path):
    t = [1000.0]
    p = Pairing(tmp_path / "remote.json", clock=lambda: t[0])
    code = p.new_code()
    t[0] += 181
    assert p.pair(code) is None  # three minutes, then gone
    code = p.new_code()
    for _ in range(TRIES):
        p.pair("000000" if code != "000000" else "111111")
    assert p.pair(code) is None  # five wrong tries end the code


def _request(port, path, body=None, cookie=None, host=None, origin=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    if cookie:
        req.add_header("Cookie", cookie)
    if host:
        req.add_header("Host", host)
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}"), r.headers.get("Set-Cookie")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}") if "json" in (e.headers.get("Content-Type") or "") else {}, None


def test_the_phone_gets_nothing_until_paired_then_asks_and_sees(tmp_path):
    state, asked = ScreenState(), []
    state.said("There it is! I see your keys.", "device")
    pairing = Pairing(tmp_path / "remote.json")
    server = serve_remote(state, pairing, lambda text: asked.append(text) or "ok", "127.0.0.1", 0)
    port = server.server_address[1]
    try:
        assert _request(port, "/state")[0] == 401  # what Andy is doing: not even that, unpaired
        assert _request(port, "/ask", {"text": "where are my keys"})[0] == 401 and asked == []
        assert _request(port, "/state", host="evil.example:80")[0] == 403  # asked by another name: DNS rebinding
        code = pairing.new_code()
        assert _request(port, "/pair", {"code": code}, origin="http://evil.example")[0] == 403  # another site's page
        status, body, cookie = _request(port, "/pair", {"code": code})
        assert status == 200 and body["paired"] and "HttpOnly" in cookie and "SameSite=Strict" in cookie
        key = cookie.split(";")[0]
        status, body, _ = _request(port, "/state", cookie=key)
        assert status == 200 and body["caption"] == "There it is! I see your keys."
        assert _request(port, "/ask", {"text": "  where are   my keys "}, cookie=key)[1] == {"answer": "ok"}
        assert asked == ["where are my keys"]
    finally:
        server.shutdown()


def test_the_phone_sees_the_find_but_not_the_rest_of_the_tv():
    snap = {"state": "Pointing", "caption": "There it is!", "picture": {"src": "data:...", "width": 1920, "height": 1080,
            "box": [1, 2, 3, 4], "outline": "M 0 0", "scale": [1, 1], "label": "keys", "words": "w", "aim_deg": 2,
            "metres": 0.6, "seconds_left": 100}, "watching": ["keys: on the desk"], "next": {"text": "call Sam"},
            "outbox": [{"to": "Muse Spark", "words": "weather?"}], "models": [{"name": "SAM 3.1"}]}
    out = phone_state(snap)
    assert out["picture"]["label"] == "keys" and out["sent"] == [{"to": "Muse Spark", "words": "weather?"}]
    assert "watching" not in out and "next" not in out  # the phone needs the find, not the household's lists


@pytest.mark.parametrize("said, kind", [("Andy, connect my phone", "pair_phone"), ("pair my phone please", "pair_phone"),
                                        ("Andy, forget my phones", "forget_phones"), ("forget my phone", "forget")])
def test_pairing_is_asked_for_in_plain_words(said, kind):
    assert parse(said).kind == kind


def test_andy_pairs_a_phone_on_the_tv_and_takes_its_turns(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    assert "started with the remote turned on" in a.hear("Andy, connect my phone")
    a.pairing, a.remote_url = Pairing(tmp_path / "remote.json"), "http://192.168.1.10:8766"
    assert "type the six numbers" in a.hear("Andy, connect my phone")
    card = a.screen.snapshot()["pairing"]
    assert card["url"] == "http://192.168.1.10:8766" and len(card["code"]) == 6 and card["left"] > 170
    done = threading.Event()
    a.hear, real = (lambda text: (real(text), done.set())), a.hear
    assert a.ask_from_phone("what time is it") == "ok"
    assert done.wait(5)
    held = threading.Event()

    def busy_turn():
        with a.lock:
            held.set()
            done.clear()
            done.wait(2)

    threading.Thread(target=busy_turn).start()
    held.wait(2)
    assert a.ask_from_phone("where are my keys") == "busy"
    done.set()
