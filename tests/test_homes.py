import datetime as dt

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.memory.places import Places
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.remote import phone_state
from tests.test_app import andy, said


def test_a_home_is_kept_with_its_words_and_forgetting_the_thing_forgets_it(tmp_path):
    p = Places(tmp_path / "places.json")
    p.watch("keys")
    p.set_home("keys", -20.0, 25.0, 0.6, "", when=1.0)
    p.saw("keys", -21.0, 25.5, when=2.0)
    p.near("keys", "on the desk, next to the lamp")
    assert p.home_words("keys") == "on the desk, next to the lamp"  # the words of a sighting there, written later
    assert p.at_home("keys", -18.0, 24.0) and not p.at_home("keys", 30.0, 25.0)
    assert Places(tmp_path / "places.json").home("keys")["metres"] == 0.6  # kept
    p.forget("keys")
    assert p.homes() == {}


def test_my_keys_live_here_then_everything_is_home(tmp_path):
    a, body, _ = andy(Thing("keys", -20.0, 25.0), Thing("glasses", -5.0, 20.0), tmp_path=tmp_path)
    words = a.hear("Hey Andy, my keys live here")
    assert "Got it: your keys live next to the glasses." in words and "every evening at 9" in words  # after the AI disclosure
    assert "keys" in a.places.watching() and a.places.home("keys")["yaw"] == pytest.approx(-20.0, abs=1)
    a.hear("my glasses live here")
    assert a.hear("is everything home?") == "Everything's home: your keys and your glasses."
    assert a.screen.snapshot()["homes"]["rows"][0]["status"] == "home"


def test_a_thing_away_is_pointed_at_then_its_home(tmp_path):
    keys = Thing("keys", -20.0, 25.0)
    a, body, _ = andy(keys, Thing("glasses", -5.0, 20.0), tmp_path=tmp_path)
    a.hear("my keys live here")
    a.hear("my glasses live here")
    keys.yaw = 45.0  # left on the other side of the table
    body.log.clear()
    words = a.hear("are all my things where they belong?")
    spoken = said(body)
    assert "Your glasses is home." not in spoken and "Your glasses are home." in spoken
    assert any(w.startswith("Your keys aren't home: they are a little to my left") or w.startswith("Your keys aren't home: they are to my left")
               for w in spoken)
    assert words == "They live there, next to the glasses."
    points = [e for e in body.log if e[0] == "point"]
    assert abs(points[-2][1] - 45.0) < 5 and abs(points[-1][1] + 20.0) < 5  # where it is, then where it lives
    rows = {r["thing"]: r["status"] for r in a.screen.snapshot()["homes"]["rows"]}
    assert rows == {"keys": "away", "glasses": "home"}


def test_a_thing_not_seen_anywhere_is_looked_for_later(tmp_path):
    keys = Thing("keys", -20.0, 25.0)
    a, body, _ = andy(keys, tmp_path=tmp_path)
    a.hear("my keys live here")
    body.room.things.remove(keys)
    words = a.hear("is everything home?")
    assert words == "I can't see your keys anywhere; they live on its own. I'll keep looking." or "I'll keep looking." in words
    assert a.lost.looking() == ["keys"]


def test_a_search_looks_at_home_first_and_says_so(tmp_path):
    a, body, _ = andy(Thing("keys", -20.0, 25.0), Thing("glasses", -5.0, 20.0), tmp_path=tmp_path)
    a.hear("my keys live here")
    a.places._data["seen"].pop("keys")  # last seen forgotten: the home is the first look
    body.log.clear()
    words = a.hear("where are my keys?")
    assert "Right at home, where they live." in words
    looks = [e for e in body.log if e[0] == "look"]
    assert abs(looks[0][1] + 20.0) < 5  # its home, first


def test_no_homes_yet_and_where_does_it_live_and_forgetting_a_home(tmp_path):
    a, _, _ = andy(Thing("keys", -20.0, 25.0), Thing("glasses", -5.0, 20.0), tmp_path=tmp_path)
    assert "None of your things has a home yet" in a.hear("is everything home?")
    assert "no home yet" in a.hear("where do my keys live?")
    a.hear("my keys live here")
    assert a.hear("where do my keys live?") == "Your keys live next to the glasses."
    assert a.hear("forget my keys' home") == "Okay, your keys have no home now." and a.places.homes() == {}


def test_it_cant_set_a_home_for_what_it_cant_see_and_promises_nothing(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "I can't see your keys from here. Put them where they live" in a.hear("my keys live here")
    assert a.lost.looking() == [] and a.places.homes() == {}


def test_each_evening_at_nine_andy_checks_once(tmp_path):
    a, body, clock = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.hear("my keys live here")
    nine = dt.datetime.fromtimestamp(clock.t).replace(hour=21, minute=0, second=5)
    clock.t = nine.timestamp()
    body.log.clear()
    a.tick()
    spoken = said(body)
    assert any("It's 9 o'clock: let me check your things are home." in w for w in spoken)
    assert spoken[-1] == "Everything's home for the night: your keys."
    body.log.clear()
    clock.t += 600
    a.tick()
    assert not any("9 o'clock" in w for w in said(body))  # once a day


@pytest.mark.parametrize("text, kind, thing", [
    ("Hey Andy, my keys live here", "home_set", "keys"), ("this is where my glasses go", "home_set", "glasses"),
    ("mis llaves viven aquí", "home_set", "keys"), ("is everything home?", "home_check", ""),
    ("bedtime check", "home_check", ""), ("where do my keys live?", "home_where", "keys"),
    ("forget my keys' home", "home_forget", "keys"), ("my kids live here", "chat", ""), ("I live here", "chat", "")])
def test_homes_are_asked_for_in_plain_words(text, kind, thing):
    i = parse(text)
    assert (i.kind, i.thing) == (kind, thing)


def test_the_phone_sees_the_last_home_check():
    rows = [{"thing": "keys", "status": "away", "now": "to my left", "home": "the bowl"}]
    assert phone_state({"homes": {"rows": rows, "evening": False}})["homes"] == rows
