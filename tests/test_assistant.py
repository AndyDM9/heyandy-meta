import datetime as dt

import pytest

from heyandy_meta.agent.assistant import needs_agent
from heyandy_meta.robot.sim import Thing
from tests.test_agent import ScriptedSpark
from tests.test_app import andy


@pytest.mark.parametrize("said, agent", [
    ("find my glasses and remind me at 5 to clean them", True),
    ("keep an eye on my keys, and then draw me a cat", True),
    ("where are my glasses", False), ("remind me at 5 to call Sam", False), ("tell me a joke", False),
    ("what are my reminders and what do you remember", True)])
def test_more_than_one_thing_at_once_goes_to_the_agent(said, agent):
    assert needs_agent(said) is agent


def test_find_then_remind_in_one_request(tmp_path):
    spark = ScriptedSpark(
        [("find", {"object": "glasses"})],
        [("set_reminder", {"what": "clean your glasses", "when": "at 5 pm"})],
        "I found your glasses on my right, and I'll remind you at five to clean them.")
    a, body, clock = andy(Thing("glasses", -40.0, 20.0), spark=spark, tmp_path=tmp_path)
    reply = a.hear("Andy, find my glasses and remind me at 5 to clean them")
    assert reply.endswith("I'll remind you at five to clean them.")
    assert any(e[0] == "point" for e in body.log)  # it really looked and pointed
    r = a.reminders.upcoming()[0]
    assert r.text == "clean your glasses" and dt.datetime.fromtimestamp(r.at).hour == 17
    snap = a.screen.snapshot()
    assert "planned it with Andy's abilities (2 steps)" in snap["reason"]
    assert {m["name"]: m["where"] for m in snap["models"]}["Muse Spark (agent)"] == "cloud"


def test_a_reminder_time_it_cant_read_is_refused_not_guessed(tmp_path):
    spark = ScriptedSpark([("set_reminder", {"what": "call Sam", "when": "sometime soonish"})],
                          "Sorry, when should I remind you?")
    a, _, _ = andy(spark=spark, tmp_path=tmp_path)
    a.hear("keep an eye on my keys and remind me sometime soonish to call Sam")
    assert a.reminders.upcoming() == []
    tool_results = [m["content"] for m in spark.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_results[0].startswith("refused: I couldn't tell when")


def test_the_first_good_morning_of_the_day_gets_a_briefing(tmp_path):
    spark = ScriptedSpark([("list_reminders", {})], [("what_i_remember", {})], "Good morning! No reminders today.",
                          "Good morning again.")
    a, _, clock = andy(spark=spark, tmp_path=tmp_path)
    assert a.hear("Good morning, Andy").endswith("Good morning! No reminders today.")
    assert "morning briefing" in spark.requests[0]["messages"][0]["content"]
    clock.t += 3600
    a.device.text = "Hello again."
    assert a.hear("good morning").endswith("Hello again.")  # the briefing is once a day; then it's conversation


def test_without_a_home_andy_asks_instead_of_guessing_the_weather(tmp_path):
    spark = ScriptedSpark("Where do you live, so I can check the weather?")
    a, _, _ = andy(spark=spark, tmp_path=tmp_path)
    a.hear("good morning")
    assert "ask them instead of guessing" in spark.requests[0]["messages"][0]["content"]
    spark2 = ScriptedSpark("Good morning! Sunny and 84 in Miami today.")
    b, _, _ = andy(spark=spark2, tmp_path=tmp_path / "b")
    b.home = "Miami, Florida"
    b.hear("good morning")
    assert "The person lives in Miami, Florida." in spark2.requests[0]["messages"][0]["content"]


def test_a_reminder_says_the_thing_not_to_the_thing(tmp_path):
    spark = ScriptedSpark([("set_reminder", {"what": "to drink some water", "when": "in two minutes"})], "Done.")
    a, _, _ = andy(spark=spark, tmp_path=tmp_path)
    a.hear("keep an eye on my cup and remind me in two minutes to drink some water")
    assert a.reminders.upcoming()[0].text == "drink some water"


@pytest.mark.parametrize("text,agent", [
    ("Keep an eye on my wallet and my glasses", True), ("Look for my keys and my glasses", True),
    ("Remind me in 10 minutes to stretch, and at 6 pm to call Sam", True),
    ("What reminders do I have, and where did you last see my keys?", True),
    ("where are my keys", False), ("remind me at 5 to call Sam and Joe", False), ("keep an eye on my keys", False)])
def test_more_than_one_of_the_same_goes_to_the_agent(text, agent):
    assert needs_agent(text) is agent


def test_the_camera_gets_the_noun_and_the_rest_is_the_hint():
    from heyandy_meta.agent.assistant import _noun

    assert _noun("blue mug, not the red one") == ("mug", "blue mug, not the red one")
    assert _noun("my reading glasses") == ("reading glasses", "")
    assert _noun("charger") == ("charger", "")
