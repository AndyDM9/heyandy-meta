import datetime as dt

import pytest

from heyandy_meta.companion.intents import parse

NOW = dt.datetime(2026, 11, 2, 14, 30)  # a Monday afternoon


@pytest.mark.parametrize("text, thing", [
    ("Where are my glasses?", "glasses"), ("where's the remote", "remote"), ("Andy, find my keys please", "keys"),
    ("Have you seen my reading glasses?", "reading glasses"), ("can you help me find my phone", "phone"),
    ("Where did I put... where is my wallet?", "wallet"), ("where is the blue mug", "blue mug")])
def test_finding(text, thing):
    i = parse(text, NOW)
    assert (i.kind, i.thing) == ("find", thing)


def test_watching_forgetting_and_remembering():
    assert parse("Keep an eye on my keys", NOW).thing == "keys"
    assert parse("keep an eye on my keys", NOW).kind == "watch"
    assert (parse("Forget my keys.", NOW).kind, parse("Forget my keys.", NOW).thing) == ("forget", "keys")
    assert parse("forget where my glasses are", NOW).thing == "glasses"
    assert parse("What do you remember?", NOW).kind == "remember"


@pytest.mark.parametrize("text, words, when, daily", [
    ("Remind me at 3 pm to call Sam", "call Sam", (15, 0, 0), False),
    ("remind me to take the bins out at 6:30pm", "take the bins out", (18, 30, 0), False),
    ("Remind me in 10 minutes to check the oven", "check the oven", (14, 40, 0), False),
    ("remind me in an hour that the plumber is coming", "the plumber is coming", (15, 30, 0), False),
    ("Remind me every day at 9 am to water the plants", "water the plants", (9, 0, 1), True),
    ("remind me at 4 to phone the library", "phone the library", (16, 0, 0), False),
    ("remind me at 2 to phone the library", "phone the library", (14, 0, 1), False),  # 2 pm has passed: tomorrow
    ("remind me at noon about lunch with Jo", "lunch with Jo", (12, 0, 1), False)])
def test_reminders(text, words, when, daily):
    i = parse(text, NOW)
    at = dt.datetime.fromtimestamp(i.at)
    assert (i.kind, i.text, i.daily) == ("remind", words, daily)
    assert (at.hour, at.minute, (at.date() - NOW.date()).days) == when


def test_a_reminder_without_a_time_asks_again():
    assert parse("remind me to call Sam", NOW) == parse("remind me", NOW) and parse("remind me", NOW).text == ""


def test_questions_about_the_world_and_conversation():
    assert parse("What's the weather tomorrow?", NOW).kind == "world"
    assert parse("When does the library open on Saturday?", NOW).kind == "world"
    assert parse("Tell me a joke", NOW).kind == "chat"
    assert parse("What are my reminders?", NOW).kind == "reminders"


@pytest.mark.parametrize("heard, kind, thing", [
    ("where am i reading glasses", "find", "reading glasses"),
    ("andy where are my keys", "find", "keys"),
    ("keep an eye on my phone please", "watch", "phone")])
def test_what_speech_to_text_hears(heard, kind, thing):
    i = parse(heard, NOW)
    assert (i.kind, i.thing) == (kind, thing)


@pytest.mark.parametrize("heard, when", [
    ("remind me at three p m to call sam", (15, 0)), ("remind me at three pm to call sam", (15, 0)),
    ("remind me at 3 p m to call sam", (15, 0)), ("remind me at four thirty to take the bins out", (16, 30)),
    ("remind me in ten minutes to check the oven", (14, 40))])
def test_spoken_times(heard, when):
    i = parse(heard, NOW)
    at = dt.datetime.fromtimestamp(i.at)
    assert i.kind == "remind" and i.text and (at.hour, at.minute) == when
