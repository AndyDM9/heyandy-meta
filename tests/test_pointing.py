import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy


@pytest.mark.parametrize("text", ["what's that?", "Andy, what is that over there?", "look where I'm pointing",
                                  "what am I pointing at", "what's that called"])
def test_asking_about_what_i_point_at(text):
    assert parse(text).kind == "pointing"


@pytest.mark.parametrize("text,kind", [("what's this?", "describe"), ("what's that noise", "chat"),
                                       ("what am I holding", "describe")])
def test_other_questions(text, kind):
    assert parse(text).kind == kind


def points(body):
    return [e for e in body.log if e[0] == "point"]


def test_andy_looks_where_the_person_points_and_points_too(tmp_path):
    lamp = Thing("lamp", 70.0, 10.0)  # well off to the left: out of the first picture
    a, body, _ = andy(lamp, Thing("lamp", -60.0, 10.0), tmp_path=tmp_path)
    body.room.pointed_at = lamp
    reply = a.hear("what's that?")
    assert "You mean the lamp?" in reply and "left" in reply
    assert points(body) and points(body)[-1][1] == pytest.approx(70.0, abs=1.5)  # the left one, not the other lamp
    assert any("pointing at: lamp" in s for s in a.screen.snapshot()["steps"])


def test_in_view_it_points_at_once(tmp_path):
    mug = Thing("mug", 8.0, 12.0)
    a, body, _ = andy(mug, tmp_path=tmp_path)
    body.room.pointed_at = mug
    assert "You mean the mug?" in a.hear("what is that over there")
    assert len([e for e in body.log if e[0] == "capture"]) <= 3  # no sweep of the room


def test_no_pointing_no_guessing(tmp_path):
    a, body, _ = andy(Thing("mug", 8.0, 12.0), tmp_path=tmp_path)
    assert "can't tell what you're pointing at" in a.hear("what's that?") and not points(body)
