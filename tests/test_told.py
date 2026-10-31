import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.memory.told import TOLD_FOR_S, Told, yours
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy, said


def test_told_places_are_kept_as_words_with_when_and_let_go_after_a_year(tmp_path):
    t = [1000.0]
    told = Told(tmp_path / "told.json", clock=lambda: t[0])
    told.tell("passport", "in the top drawer")
    t[0] += 10
    told.tell("passport", "in the safe")
    assert told.latest("passport") == {"words": "in the safe", "at": 1010.0}
    assert Told(tmp_path / "told.json", clock=lambda: t[0]).latest("passport")["words"] == "in the safe"  # kept
    t[0] += TOLD_FOR_S + 1
    assert told.latest("passport") is None and told.all() == {}
    assert told.forget("passport") and not told.forget("passport")


def test_my_words_are_said_back_as_yours():
    assert yours("in my bag, under my coat") == "in your bag, under your coat"
    assert yours("behind the books in our study") == "behind the books in your study"


def test_told_then_asked_answers_at_once_without_moving(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    assert "Got it: your passport, in the top drawer of the desk. I'll remember." in a.hear(
        "Hey Andy, I'm putting my passport in the top drawer of the desk")
    clock.t += 3 * 86400
    body.log.clear()
    words = a.hear("where's my passport?")
    assert "You told me on" in words and "your passport is in the top drawer of the desk" in words
    assert "ask me again and I'll look around the room" in words
    assert not [e for e in body.log if e[0] in ("look", "capture", "point")]  # no search: it can't see in a drawer
    assert a.screen.snapshot()["told"]["words"] == "in the top drawer of the desk"


def test_asked_again_it_looks_and_a_miss_mentions_what_was_told(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.hear("I put my spare key under the mat by the back door")
    clock.t += 3600
    a.hear("where's my spare key?")
    body.log.clear()
    words = a.hear("where's my spare key?")  # again: look around the room
    assert [e for e in body.log if e[0] == "capture"]
    assert "you told me it was under the mat by the back door" in words and "couldn't find" in words


def test_seen_since_the_camera_wins(tmp_path):
    a, body, clock = andy(Thing("glasses", 15.0, 20.0), tmp_path=tmp_path)
    a.hear("keep an eye on my glasses")
    a.hear("I've left my glasses on the bedside table")
    clock.t += 60
    a.hear("where are my glasses?")  # told more recently than seen: from the words
    a.places.saw("glasses", 15.0, 20.0, when=clock.t + 30)
    clock.t += 300
    body.log.clear()
    words = a.hear("where are my glasses?")
    assert "You told me" not in words and "glasses" in words and [e for e in body.log if e[0] == "point"]


def test_what_do_you_remember_lists_what_was_told_and_forget_removes_it(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("remember that the warranty is in the blue folder")
    assert any(line.startswith("warranty: in the blue folder (you told me at") for line in a._memory())
    a.hear("forget my warranty")
    assert a.told.latest("warranty") is None


@pytest.mark.parametrize("text, kind, thing, where", [
    ("Hey Andy, I'm putting my passport in the top drawer of the desk", "tell", "passport", "in the top drawer of the desk"),
    ("my spare key is in the kitchen drawer", "tell", "spare key", "in the kitchen drawer"),
    ("I hid my wallet behind the books in my study", "tell", "wallet", "behind the books in my study"),
    ("I put the kettle on", "chat", "", ""), ("I'm putting the kids in bed", "chat", "", ""),
    ("I'm putting my keys here", "chat", "", ""), ("where is my passport", "find", "passport", "")])
def test_telling_is_said_in_plain_words(text, kind, thing, where):
    i = parse(text)
    assert (i.kind, i.thing) == (kind, thing) and (kind != "tell" or i.text == where)


@pytest.mark.parametrize("text", ["put the weather radar on the screen", "keep your eye on the ball", "put the news on the TV"])
def test_a_command_to_put_something_isnt_telling(text):
    assert parse(text).kind != "tell"  # telling has an "I": "I'm putting", "I put", "I've left"
