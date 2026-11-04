"""The dress rehearsal's own checks: a shot that didn't do what the video needs must say so."""
import pytest

from evals import rehearsal


@pytest.mark.parametrize("reply", ["I can only make pictures when I'm connected.", "I can only use the web when I'm connected.",
                                   "I'm not connected right now.", "I can't draw that offline."])
def test_a_cloud_shot_that_stayed_home_is_a_problem(reply, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "set")
    assert rehearsal.cloud_missed(reply)


def test_without_the_key_a_cloud_shot_is_a_problem_whatever_was_said(monkeypatch):
    """November 1: run without ~/.config/heyandy-meta/env, both cloud shots passed."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert rehearsal.cloud_missed("Here's a lighthouse at dawn, on the TV.")


@pytest.mark.parametrize("reply", ["Here's a lighthouse at dawn, on the TV.", "Here's the weather radar, on the TV."])
def test_a_cloud_shot_that_worked_passes(reply, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "set")
    assert not rehearsal.cloud_missed(reply)


def test_the_rehearsal_says_every_line_of_the_filming_card_as_it_will_be_said():
    """November 3: the card's follow-up to the first find ("how did you do that?") wasn't rehearsed, and the rehearsal
    said "Andy, speak English" where the card says "Hey Andy, speak English"."""
    lines = [line for _, _, line, _ in rehearsal.SHOTS]
    assert lines[:2] == ["Hey Andy, where are my glasses?", "Hey Andy, how did you do that?"]
    assert "Hey Andy, speak English." in lines and "Andy, speak English." not in lines
    assert all(line.startswith("Hey Andy") or line.startswith("安迪") for line in lines)  # the name, every time
