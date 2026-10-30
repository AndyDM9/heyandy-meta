import os

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.memory.mine import Mine, likeness
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy


def test_a_thing_is_kept_as_numbers_and_forgotten(tmp_path):
    mine = Mine(tmp_path / "mine.json")
    mine.learn("coffee mug", [[1.0, 0.0], [0.9, 0.1]], now=1.0)
    assert mine.knows("mug") and mine.key("mug") == "coffee mug"  # "mug" means the coffee mug
    assert mine.how_alike("mug", [1.0, 0.0]) == pytest.approx(1.0)
    assert mine.how_alike("keys", [1.0, 0.0]) is None
    assert os.stat(tmp_path / "mine.json").st_mode & 0o777 == 0o600
    assert Mine(tmp_path / "mine.json").knows("coffee mug")  # kept across restarts
    assert mine.forget("mug") and not Mine(tmp_path / "mine.json").knows("coffee mug")


def test_likeness():
    assert likeness([1, 0], [0, 1]) == 0 and likeness([2, 0], [1, 0]) == pytest.approx(1.0)


@pytest.mark.parametrize("text,thing", [("this is my mug", "mug"), ("Andy, this is my coffee mug.", "coffee mug"),
                                        ("this cup is mine", "cup"), ("learn what my keys look like", "keys"),
                                        ("that's my water bottle", "water bottle")])
def test_asking_andy_to_learn_a_thing(text, thing):
    i = parse(text)
    assert (i.kind, i.thing) == ("mine", thing)


def test_whats_this_is_still_a_question():
    assert parse("what's this?").kind == "describe"


def test_andy_learns_my_mug_and_skips_someone_elses(tmp_path):
    blue, red = Thing("mug", 0.0, 12.0, looks="blue"), Thing("mug", 18.0, 15.0, looks="red")
    a, body, _ = andy(blue, tmp_path=tmp_path)
    reply = a.hear("this is my mug")
    assert "I'll know your mug" in reply and "never a picture" in reply
    assert a.mine.knows("mug")

    blue.yaw, blue.pitch = -55.0, 15.0  # mine is put away to the right; someone else's is right in front
    body.room.things.append(red)
    reply = a.hear("where is my mug?")
    assert "the one you showed me" in reply and "right" in reply
    assert reply.endswith("The other mug isn't yours.")  # it looked at that one first, and says why it passed
    steps = a.screen.snapshot()["steps"]
    assert any("like yours" in s for s in steps)


def test_only_someone_elses_mug_in_the_room(tmp_path):
    blue, red = Thing("mug", 0.0, 12.0, looks="blue"), Thing("mug", 18.0, 15.0, looks="red")
    a, body, _ = andy(blue, tmp_path=tmp_path)
    a.hear("this is my mug")
    body.room.things[:] = [red]
    assert "but not yours" in a.hear("where is my mug?")


def test_forgetting_my_mug_forgets_what_it_looks_like(tmp_path):
    a, _, _ = andy(Thing("mug", 0.0, 12.0, looks="blue"), tmp_path=tmp_path)
    a.hear("this is my mug")
    assert "what it looks like" in a.hear("forget my mug") and not a.mine.knows("mug")


def test_nothing_held_up_nothing_learned(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "couldn't see your mug" in a.hear("this is my mug") and not a.mine.knows("mug")


def test_house_keys_are_not_car_keys(tmp_path):
    mine = Mine(tmp_path / "mine.json")
    mine.learn("car keys", [[1.0, 0.0]])
    assert mine.key("keys") == "car keys" and mine.key("house keys") is None
    assert not mine.forget("house keys") and mine.knows("car keys")
    mine.learn("mug", [[1.0, 0.0]])
    assert mine.key("coffee mug") == "mug"


@pytest.mark.parametrize("text", ["that's my point", "this is my friend sarah", "here's my question",
                                  "this is my first time", "learn my face"])
def test_conversation_is_not_learning_a_thing(text):
    assert parse(text).kind != "mine"


def test_keeping_an_eye_wins_over_learning():
    assert parse("this is my wallet, keep an eye on it").kind == "watch"
