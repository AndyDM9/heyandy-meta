import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.memory.lost import LOOK_EVERY_S, LOOK_FOR_S, Lost, spot
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing
from heyandy_meta.screen.remote import phone_state
from tests.test_app import andy, said


def test_a_promise_is_kept_for_two_hours_with_its_first_time_and_its_looks(tmp_path):
    t = [1000.0]
    lost = Lost(tmp_path / "lost.json", clock=lambda: t[0])
    assert lost.add("wallet") and not lost.add("wallet")  # asked again: the same promise, its first time kept
    lost.add("keys")
    lost.looked(["wallet"])
    assert lost.looking() == ["wallet", "keys"] and lost.looks("wallet") == 1 and lost.since("wallet") == 1000.0
    assert Lost(tmp_path / "lost.json", clock=lambda: t[0]).looking() == ["wallet", "keys"]  # a restart keeps looking
    assert lost.drop("keys") == ["keys"] and lost.looking() == ["wallet"]
    t[0] += LOOK_FOR_S + 1
    assert lost.looking() == []  # two hours on, let go
    assert '"wallet"' not in (tmp_path / "lost.json").read_text()


def test_one_look_around_spots_several_things_at_once():
    room = Room([Thing("wallet", 35.0, 20.0), Thing("keys", -30.0, 25.0)])
    body = SimBody(room)
    assert set(spot(body, SimSegmenter(room), ["wallet", "keys", "phone"])) == {"wallet", "keys"}


def test_a_missed_search_promises_to_keep_looking_and_asked_again_says_how_hard(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    words = a.hear("where is my wallet")
    assert "I'll keep looking, and tell you when I see it." in words and "Where did you last have it?" in words
    assert [x["thing"] for x in a.screen.snapshot()["lost"]] == ["wallet"]
    clock.t += LOOK_EVERY_S
    a.tick()  # a look around: nothing
    words = a.hear("where is my wallet")
    assert "Still no sign of it: I've looked 1 time since" in words and "I'll keep at it." in words


def test_it_turns_up_andy_looks_again_finds_it_points_and_says_so(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.hear("where are my keys")
    body.room.things.append(Thing("keys", -25.0, 22.0))  # put back on the table while Andy wasn't asked
    body.log.clear()
    clock.t += LOOK_EVERY_S - 1
    a.tick()
    assert not [e for e in body.log if e[0] == "say"]  # not yet: every few minutes, not all the time
    clock.t += 1
    a.tick()
    spoken = said(body)
    assert spoken[-1].startswith("Good news: your keys turned up! They're a little to my right")
    assert "I'd been looking out for them since" in spoken[-1]
    assert "Let me look." not in spoken  # a search of Andy's own doesn't announce itself
    assert ("chime", "found") in body.log and any(e[0] == "point" for e in body.log)
    assert a.lost.looking() == [] and a.screen.snapshot()["lost"] == []


def test_a_glimpse_the_search_doesnt_confirm_is_kept_quiet(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.hear("where is my wallet")
    body.room.things.append(Thing("wallet", 30.0, 20.0, on_screen=True))  # a picture of one on the TV
    body.log.clear()
    clock.t += LOOK_EVERY_S
    a.tick()
    assert said(body) == [] and not [e for e in body.log if e[0] == "emote"]  # no words, no "oops"
    assert a.lost.looking() == ["wallet"]


def test_quiet_time_waits_and_a_find_the_person_asked_for_ends_the_promise(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.hear("where is my wallet")
    a.quiet_until = clock.t + 3600
    body.log.clear()
    clock.t += LOOK_EVERY_S
    a.tick()
    assert not [e for e in body.log if e[0] == "capture"]  # be quiet: no looking around either
    body.room.things.append(Thing("wallet", 30.0, 20.0))
    a.quiet_until = 0.0
    a.hear("where is my wallet")  # asked, and found: no need to keep looking
    assert a.lost.looking() == []


@pytest.mark.parametrize("words, reply, left", [
    ("I found my wallet", "Glad your wallet turned up!", ["keys"]),
    ("oh never mind, found it", "Glad it turned up!", []),
    ("stop looking for the keys", "Okay, I'll stop looking for your keys.", ["wallet"]),
    ("you can stop looking", "Okay, I'll stop looking for your wallet and your keys.", []),
])
def test_found_it_and_stop_looking(tmp_path, words, reply, left):
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("where is my wallet")
    a.hear("where are my keys")
    assert a.hear(words) == reply and a.lost.looking() == left


def test_what_are_you_looking_for(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "Nothing right now" in a.hear("what are you looking for?")
    a.hear("where is my wallet")
    assert a.hear("Andy, what are you still looking for?") == "I'm still looking for your wallet. I'll tell you when I see it."


@pytest.mark.parametrize("text, kind", [("I found it hard to sleep", "chat"), ("Ya lo encontré", "lost_done"),
                                        ("deja de buscar", "lost_done"), ("I lost my keys", "find")])
def test_lost_and_found_words_and_near_misses(text, kind):
    assert parse(text).kind == kind


def test_the_phone_sees_what_andy_is_still_looking_for():
    assert phone_state({"lost": [{"thing": "wallet", "since": 1.0, "looks": 2}]})["lost"] == ["wallet"]


def test_the_tv_card_says_it_turned_up():
    from heyandy_meta.finder.search import Found
    from heyandy_meta.models.common import Mask
    from heyandy_meta.robot.body import Frame
    from heyandy_meta.screen.state import ScreenState

    s = ScreenState()
    mask = Mask("mug", (10, 10, 50, 50), 0.9, (30.0, 30.0))
    s.found(Found("mug", 0.0, 10.0, 0.9, Frame(b"\xff\xd8jpeg", 1920, 1080, 0.0, 10.0), mask, 1), "There it is!")
    assert not s.snapshot()["picture"]["turned"]
    s.turned_up("Good news: your mug turned up!")
    p = s.snapshot()["picture"]
    assert p["turned"] and p["words"] == "Good news: your mug turned up!"
