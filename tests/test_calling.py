import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.voice.loop import VoiceLoop
from tests.test_app import andy
from tests.test_voice import Andy as FakeAndy


def test_hey_andy_only_ignores_plain_andy_but_follow_ups_still_need_no_name():
    t = [0.0]
    a = FakeAndy()
    a.hey_only = True
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    assert loop.heard("Andy, can you pass the salt") is None  # someone called Andy, being talked to
    t[0] += 60
    assert loop.heard("hey andy where are my glasses") == "ok"
    assert loop.heard("and my keys?") == "ok"  # a follow-up, within the window: no name needed
    t[0] += 60
    assert loop.heard("oye andy dónde están mis gafas") == "ok"  # the Spanish greeting counts
    a.hey_only = False
    t[0] += 60
    assert loop.heard("Andy, where's my phone") == "ok"  # plain "Andy" again, when allowed


@pytest.mark.parametrize("said, how", [("Andy, only answer to 'Hey Andy'", "hey only"),
                                       ("hey andy, answer only to hey andy please", "hey only"),
                                       ("hey andy, answer to Andy too", "any"), ("plain Andy is fine", "any")])
def test_how_andy_is_called_is_asked_for_in_plain_words(said, how):
    i = parse(said)
    assert (i.kind, i.thing) == ("calling", how)


def test_the_choice_is_said_and_remembered(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "only answer to 'Hey Andy'" in a.hear("only answer to hey andy")
    b, _, _ = andy(tmp_path=tmp_path)  # Andy started again, on the same computer
    b.load_voice()
    assert b.hey_only
    assert "plain 'Andy' too" in b.hear("answer to Andy too") and not b.hey_only
