import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy


@pytest.mark.parametrize("text", ["Andy, I'm going out", "I'm heading out now", "we're going to the store",
                                  "do I have everything?", "am I forgetting anything", "I'm leaving the house"])
def test_going_out(text):
    assert parse(text).kind == "going_out"


@pytest.mark.parametrize("text", ["where are my keys", "I'm going to bed", "the cat is going out of her mind"])
def test_not_going_out(text):
    assert parse(text).kind != "going_out"


def test_andy_points_at_what_is_still_here_and_mentions_the_next_reminder(tmp_path):
    keys, wallet = Thing("keys", 40.0, 20.0), Thing("wallet", -30.0, 18.0)
    a, body, clock = andy(keys, tmp_path=tmp_path)
    for t in (keys, wallet):
        a.places.watch(t.label)
        a.places.saw(t.label, t.yaw, t.pitch, when=clock())
    a.reminders.add("call Sam", clock() + 3600, now=clock())  # the wallet isn't in the room any more: it went
    reply = a.hear("I'm going out")
    assert "Don't forget your keys." in reply and "didn't see your wallet" in reply and "with you" in reply
    assert "Remember: at" in reply and "call Sam" in reply and reply.endswith("Have a lovely time!")
    points = [e for e in body.log if e[0] == "point"]
    assert len(points) == 1 and points[0][1] == pytest.approx(40.0, abs=1.0)  # pointed at the keys only
    assert "Your keys are still here" in " ".join(e[1] for e in body.log if e[0] == "say")
    check = a.screen.snapshot()["checklist"]
    assert [(i["thing"], i["here"]) for i in check["items"]] == [("keys", True), ("wallet", False)]


def test_nothing_watched_asks_about_the_usual_things(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path, online=False)
    reply = a.hear("I'm heading out")
    assert "keys, your wallet and your phone" in reply and not [e for e in body.log if e[0] == "point"]


@pytest.mark.parametrize("text,kind", [("where are my keys? I'm going out", "find"), ("I'm leaving you a note", "chat"),
                                       ("I'm leaving for work", "going_out"), ("I'm going out, keep an eye on my keys", "watch")])
def test_going_out_doesnt_swallow_other_requests(text, kind):
    assert parse(text).kind == kind
