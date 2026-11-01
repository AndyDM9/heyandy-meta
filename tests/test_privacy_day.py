import datetime as dt
from types import SimpleNamespace as NS

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy


@pytest.mark.parametrize("text", ["Andy, what did you send to the cloud today?", "what has left the house today",
                                  "What went to the cloud?", "privacy report please", "what have you shared today?",
                                  "what left my home today?"])
def test_asking_what_left_the_house(text):
    assert parse(text).kind == "privacy"


@pytest.mark.parametrize("text", ["where are my keys", "remind me to send the letter", "what's the weather today",
                                  "what did you see?"])
def test_not_a_privacy_question(text):
    assert parse(text).kind != "privacy"


def weather(tmp_path):
    cite = NS(type="url_citation", url="https://www.weather.gov/x", title="Forecast")
    resp = NS(output_text="Sunny.", usage=None, output=[NS(content=[NS(annotations=[cite])])])
    calls = []
    a, body, clock = andy(Thing("keys", 20.0, 20.0), spark=NS(responses=NS(create=lambda **kw: calls.append(kw) or resp)),
                          tmp_path=tmp_path)
    return a, calls


def test_the_day_is_counted_from_the_receipts_and_asking_sends_nothing(tmp_path):
    a, calls = weather(tmp_path)
    a.hear("where are my keys")
    a.hear("what's the weather tomorrow?")
    a.hear("Lovely")
    before = len(calls)
    reply = a.hear("Andy, what did you send to the cloud today?")
    assert len(calls) == before and a.screen.snapshot()["outbox"] == []  # answered here: nothing sent to answer it
    assert "2 of your 3 requests stayed in this house" in reply
    assert "For the other 1, I sent 4 words to Muse Spark." in reply  # "what's the weather tomorrow?"
    assert "No camera pictures and no sound left the house." in reply
    card = a.screen.snapshot()["privacy"]
    assert card["title"] == "2 of 3 requests stayed in this house"
    assert [r["mark"] for r in card["rows"]] == ["✓", "→", "→", "✓"]
    assert card["rows"][1]["text"] == "Muse Spark: words from 1 request"


def test_a_day_with_nothing_sent(tmp_path):
    a, _, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path, online=False)
    a.hear("where are my keys")
    a.hear("Lovely")
    reply = a.hear("what has left the house today?")
    assert "nothing has left this house: all 2 of your requests were answered on this computer." in reply
    assert a.screen.snapshot()["privacy"]["title"] == "Nothing has left this house"
    a.hear("where are my keys")  # what happens next takes the card's place
    assert a.screen.snapshot()["privacy"] is None


def test_crisis_turns_count_as_staying_home(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("I want to die")
    assert a.hear("privacy report").endswith("nothing has left this house.")
    assert a.screen.day().turns == 1  # the crisis turn (the question itself is still going)


def test_screenshots_and_staged_pictures_are_counted_not_kept():
    now = [dt.datetime(2026, 11, 3, 23, 0).timestamp()]
    s = ScreenState(now=lambda: now[0])
    s.new_turn()
    s.sent("Muse Spark (web search)", "show me the weather radar")
    s.screenshots_sent("Muse Spark (computer use)", 3)
    s.new_turn()
    s.used("SAM 3.1 (Model API)", "cloud", 5)
    s.new_turn()
    d = s.day()
    assert (d.turns, d.went, d.words, d.screenshots, d.pictures) == (2, 2, 5, 3, 5)
    assert d.to == {"Muse Spark": 1, "SAM 3.1": 1}
    assert not hasattr(d, "outbox")  # counts only: the words themselves stay on their own turn's receipt
    now[0] += 2 * 3600  # past midnight: a new day, counted from midnight
    d = s.day()
    assert (d.turns, d.words, d.date) == (0, 0, dt.date(2026, 11, 4))
    assert d.since == dt.datetime(2026, 11, 4).timestamp()


def test_since_andy_started_when_it_started_today():
    from heyandy_meta.app import Andy

    started = dt.datetime(2026, 11, 3, 9, 12).timestamp()
    screen = ScreenState(now=lambda: started)
    a = NS(screen=screen, _source="", _reason="", _privacy_card=lambda t, rows, promises=False: screen.privacy_day(t, rows))
    assert Andy.privacy_today(a) == "Since I started at 9:12, nothing has left this house."
    assert screen.privacy["title"] == "Nothing has left this house"


def test_the_rest_of_a_combined_request_is_answered_too(tmp_path):
    a, _, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path, online=False)
    reply = a.hear("Andy, what did you send to the cloud today, and where are my keys?")
    assert "nothing has left this house." in reply and reply.endswith("I see your keys, a little to my left.")
    assert a.hear("privacy report please").endswith("nothing has left this house.")  # the combined request: one turn
    assert a.screen.day().turns == 1  # a turn counts once the next one starts
