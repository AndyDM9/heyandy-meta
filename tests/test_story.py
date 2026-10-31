import datetime as dt

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.memory.places import Places
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy

DESK, DOOR, SOFA = (-20.0, 25.0), (60.0, 20.0), (100.0, 15.0)


def test_memory_knows_how_it_knew_and_a_pick_up_closes_the_place(tmp_path):
    p = Places(tmp_path / "places.json")
    p.watch("keys")
    p.saw("keys", *DESK, when=100.0, how="found")
    p.saw("keys", *DOOR, when=200.0, how="noticed")
    assert [h["how"] for h in p.history("keys")] == ["found", "noticed"]
    assert p.last_seen("keys", now=250.0) == DOOR
    p.picked_up("keys", when=300.0)
    assert p.history("keys")[-1]["gone"] == 300.0 and p.last_seen("keys", now=310.0) is None  # not there any more
    p.saw("keys", *DOOR, when=400.0, how="glanced")  # back at the door later: a new place in its story
    assert [h["how"] for h in p.history("keys")] == ["found", "noticed", "glanced"]


def test_habits_need_two_visits_and_count_them(tmp_path):
    p = Places(tmp_path / "places.json")
    p.watch("keys")
    for i, spot in enumerate((DESK, DOOR, DESK, SOFA, DESK)):
        p.saw("keys", *spot, when=100.0 * (i + 1))
    p.near("keys", "on the desk, behind the keyboard")
    usual = p.usual("keys")
    assert (usual["yaw"], usual["count"], usual["of"], usual["near"]) == (DESK[0], 3, 5, "on the desk, behind the keyboard")
    p.watch("glasses")
    p.saw("glasses", *DESK, when=100.0)
    p.saw("glasses", *DOOR, when=200.0)
    assert p.usual("glasses") is None  # never twice in one place yet


def test_the_finder_tries_the_usual_place_when_the_last_one_is_empty(tmp_path):
    a, body, clock = andy(Thing("keys", *DESK), tmp_path=tmp_path)
    a.places.watch("keys")
    for i, spot in enumerate((DESK, DOOR, DESK, SOFA)):  # usually on the desk; last seen by the sofa
        a.places.saw("keys", *spot, when=clock() - 600 + 100 * i)
    said = a.hear("where are my keys")
    looks = [e for e in body.log if e[0] == "look"]
    assert "Right where you usually leave them." in said
    assert abs(looks[1][1] - DESK[0]) < 2  # the sofa first (last seen), then straight to the desk: no sweep
    assert len([e for e in looks if abs(e[1] - SOFA[0]) < 2]) >= 1


def test_what_happened_to_my_keys_is_told_and_drawn(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    today = dt.datetime.fromtimestamp(clock()).replace(hour=8, minute=12).timestamp()
    clock.t = today + 4 * 3600
    a.places.watch("keys")
    a.places.saw("keys", *DESK, when=today, how="found")
    a.places.near("keys", "on the desk, behind the keyboard")
    a.places.saw("keys", *DOOR, when=today + 2.5 * 3600, how="noticed")
    a.places.near("keys", "on the shelf by the door")
    a.places.picked_up("keys", when=today + 3 * 3600)
    a.places.saw("keys", *DESK, when=today + 3.5 * 3600, how="glanced")
    said = a.hear("Andy, what happened to my keys today?")
    assert "At 8:12, I found them on the desk, behind the keyboard" in said
    assert "you put them down on the shelf by the door" in said and "you picked them up" in said.lower()
    assert "usually end up on the desk" in said
    tl = a.screen.snapshot()["timeline"]
    assert tl["thing"] == "keys" and [x["how"] for x in tl["items"]] == ["found", "noticed", "picked up", "glanced"]
    assert tl["usual"]["count"] == 2 and "behind the keyboard" in tl["usual"]["words"]
    usual = a.hear("where do I usually leave my keys?")
    assert "Usually on the desk" in usual and "If they aren't where I last saw them" in usual
    assert "not keeping an eye on your wallet" in a.hear("what happened to my wallet?")


@pytest.mark.parametrize("said, kind, thing", [
    ("Andy, what happened to my keys today?", "story", "keys"), ("where have my glasses been?", "story", "glasses"),
    ("where do I usually leave my keys?", "usual", "keys"), ("where are my keys usually?", "usual", "keys"),
    ("what happened to the world today?", "chat", ""), ("where are my keys?", "find", "keys")])
def test_the_story_and_the_habit_are_asked_for_in_plain_words(said, kind, thing):
    i = parse(said)
    assert (i.kind, i.thing) == (kind, thing)


def test_the_agent_has_both_as_tools():
    from heyandy_meta.agent.assistant import TOOLS

    names = {t["function"]["name"] for t in TOOLS}
    assert {"story_of", "usual_place"} <= names
