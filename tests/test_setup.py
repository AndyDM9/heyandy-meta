import pytest

from heyandy_meta.app import things_in
from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.safety import CRISIS_REPLY
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy


def test_lets_get_started_watches_what_you_lose_points_at_it_and_ends_with_a_try(tmp_path):
    a, body, _ = andy(Thing("keys", -20.0, 25.0), Thing("glasses", 15.0, 20.0), tmp_path=tmp_path)
    assert not a.setup_done
    said = a.hear("Andy, let's get started")
    assert "what do you lose most often" in said.lower() and a.screen.snapshot()["setup"]["step"] == "things"
    assert any("stays in this house" in e[1] for e in body.log if e[0] == "say")  # the promise, first
    body.log.clear()
    said = a.hear("my keys and my glasses")
    assert set(a.places.watching()) == {"keys", "glasses"}
    points = [e for e in body.log if e[0] == "point"]
    assert len(points) == 2 and {round(p[1]) for p in points} == {-20, 15}  # it pointed at each one it saw
    assert "There are your keys." in [e[1] for e in body.log if e[0] == "say"]
    assert "Now try me: say, 'Hey Andy, where are my keys?'" in said
    assert "I'll keep an eye on your keys and your glasses." in said and "your your" not in said
    assert a.screen.snapshot()["setup"] == {"step": "try", "thing": "keys"}
    said = a.hear("Andy, where are my keys?")
    assert "keys" in said and "You're all set" in said and a.setup_done
    assert a.screen.snapshot()["setup"]["step"] == "done"


def test_no_thing_named_is_asked_once_more_and_skip_ends_it(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("let's get started")
    assert "For example" in a.hear("hmm, not sure")
    assert "tell me later" in a.hear("I really don't know")
    b, _, _ = andy(tmp_path=tmp_path / "b")
    b.hear("let's get started")
    assert "leave it there" in b.hear("skip") and b.screen.snapshot()["setup"] is None and not b.setup_done


def test_crisis_words_come_first_even_mid_setup(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("let's get started")
    assert a.hear("I want to die") == CRISIS_REPLY


@pytest.mark.parametrize("said, things", [("my keys and my reading glasses", ["keys", "reading glasses"]),
                                          ("the remote, my phone", ["remote", "phone"]), ("glasses mostly", ["glasses"]),
                                          ("nothing really", [])])
def test_the_things_in_an_answer(said, things):
    assert things_in(said) == things


@pytest.mark.parametrize("said", ["Andy, let's get started", "set yourself up", "show me how you work", "start the tour"])
def test_the_setup_is_asked_for_in_plain_words(said):
    assert parse(said).kind == "setup"


def test_a_notice_names_the_thing_once(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.noticed({"kind": "put", "things": ["keys"], "masks": {}, "frame": None})
    assert a.screen.snapshot()["notice"] == "Noticed: your keys, put down"
