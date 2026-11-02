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
    ("wears the cup", "find", "cup"),
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


@pytest.mark.parametrize("text, hint", [
    ("where are my glasses", False), ("Andy, where are my reading glasses please?", False),
    ("where are my glasses, I think I left them by the TV", True), ("I lost my keys in the kitchen", True),
    ("have you seen my phone? it was on the sofa", True),
    ("where is the blue mug", True)])  # a colour says which one: the planner compares the look-alikes (2026-10-28)
def test_a_hint_is_more_than_what_to_find(text, hint):
    i = parse(text, NOW)
    assert i.kind == "find" and i.hint is hint


def test_a_colour_says_which_one_so_the_planner_compares():
    assert parse("Andy, where's the blue mug?").hint and parse("where is my red phone").hint
    assert not parse("where's my mug").hint and not parse("where are my glasses").hint


@pytest.mark.parametrize("said, kind, thing", [
    ("what's today's weather?", "world", ""), ("what is today's news", "world", ""),
    ("what time is it in Tokyo?", "world", ""), ("what's today?", "time", "day"), ("whats the time", "time", "time"),
    ("scan the room for my keys", "find", "keys"), ("measure the room and find my phone", "find", "phone"),
    ("look around the room for my glasses", "find", "glasses"), ("Andy, show me the room in 3D", "room", ""),
    ("what does the room look like?", "room", "")])
def test_the_time_the_room_and_a_search_are_told_apart(said, kind, thing):
    i = parse(said)
    assert (i.kind, i.thing) == (kind, thing)


def test_where_heard_as_was_is_a_search_only_for_a_thing_andy_knows():
    """Omnilingual ASR on the robot heard "where's the remote?" as "was the remote" (Nov 1 rehearsal)."""
    assert parse("was the remote").kind == "find" and parse("was the remote").thing == "remote"
    assert parse("was my glasses?").kind == "find"
    assert parse("was the door locked?").kind != "find" and parse("was my daughter here").kind != "find"


def test_do_you_see_is_a_search_only_for_a_thing_andy_knows():
    """Found by review (Nov 1): "do you see" made searches of warning signs, which then skipped the third look at
    conversation (app.py): never "Let me look." for these."""
    for said in ("Do you see any point in living?", "Do you see a future for me?", "Do you see any hope for me?"):
        assert parse(said).kind == "chat", said
    assert parse("Do you see my keys?").thing == "keys" and parse("Can you see the remote?").kind == "find"


def test_i_keep_getting_something_at_night_is_not_where_a_thing_is_kept():
    assert parse("I keep getting heartburn at night, what helps?").kind == "chat"
    assert parse("I keep my passport in the top drawer").kind == "tell"
    assert parse("I keep my wedding ring in the blue box").thing == "wedding ring"


@pytest.mark.parametrize("said", ["What won't you do?", "Can I trust you?", "What are your rules?", "What wouldn't you do?",
                                  "Hey Andy, what is it that you would never do?",  # Glimmer's Spanish, Nov 1
                                  "Andy, what would you absolutely never do?",  # Glimmer's Mandarin
                                  "Andy, what will you never do?"])  # Glimmer's Russian
def test_asking_andy_what_it_wont_do(said):
    assert parse(said).kind == "promises"


def test_saying_you_would_never_do_something_is_conversation():
    assert parse("I would never do that").kind == "chat" and parse("I won't do it").kind == "chat"


@pytest.mark.parametrize("said, kind", [("Can I trust you to remind me to take my pills at 8 pm?", "remind"),
                                        ("Remind me at 8 pm to take my pills, can I trust you?", "remind"),
                                        ("Can I trust you to find my glasses?", "find"),
                                        ("Where are my keys? Can I trust you?", "find")])
def test_a_request_with_can_i_trust_you_in_it_is_the_request(said, kind):
    """Found by review (Nov 1): promises took these, and no reminder was set."""
    assert parse(said).kind == kind
