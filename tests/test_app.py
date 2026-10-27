from types import SimpleNamespace

import pytest

from heyandy_meta.app import Andy
from heyandy_meta.companion.reminders import Reminders
from heyandy_meta.memory.places import Places
from heyandy_meta.models.common import Reply
from heyandy_meta.models.retry import CloudUnavailable
from heyandy_meta.robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing
from tests.test_agent import ScriptedSpark

T0 = 1_793_000_000.0  # a fixed "now" for clocks


class Device:
    def __init__(self, text="Hello there."):
        self.text, self.prompts = text, []

    def chat(self, prompt, history=()):
        self.prompts.append(prompt)
        self.history = list(history)
        return Reply(self.text, "device")


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


def andy(*things, spark=None, online=True, tmp_path=None):
    room = Room(list(things))
    body = SimBody(room)
    clock = Clock()
    a = Andy(body, SimSegmenter(room), Device(), Places(tmp_path / "places.json"),
             Reminders(tmp_path / "reminders.json"), spark=spark, judge=SimJudge(room), online=online, clock=clock)
    return a, body, clock


def said(body):
    return [e[1] for e in body.log if e[0] == "say"]


def test_first_turn_says_it_is_an_ai_and_conversation_goes_to_the_device(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    assert a.hear("Good morning") == "I'm Andy, an AI robot. Hello there."
    assert a.hear("Lovely day") == "Hello there."
    assert (a.screen.source, a.screen.reason) == ("device", "everyday turn")


def test_crisis_words_never_reach_a_model(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "988" in a.hear("I want to die")
    assert a.device.prompts == []


def test_find_on_this_computer_skips_the_picture_on_the_tv(tmp_path):
    a, body, _ = andy(Thing("glasses", 52.0, 5.0, on_screen=True), Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    reply = a.hear("Where are my glasses?")
    assert reply.endswith("I see your glasses, to my right.")
    snap = a.screen.snapshot()
    assert snap["picture"] is None and snap["running"] is False  # the pretend room has no camera picture to show
    assert snap["source"] == "device" and any("looked" in s for s in snap["steps"])


def test_a_watched_thing_is_found_where_it_was_last_seen(tmp_path):
    a, body, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("where are my keys")
    body.log.clear()
    assert a.hear("where are my keys").endswith("Right where I last saw it.")
    assert [e for e in body.log if e[0] == "capture"] == [("capture",)]  # one look, straight at the remembered place


def test_the_cloud_plans_the_search_with_words_only(tmp_path):
    spark = ScriptedSpark(
        [("look", {"object": "glasses", "views": ["far right"]})],
        [("look_closer", {"object": "glasses", "place": "1"})],
        [("point", {"place": "1"})],
        "There they are, on your right.")
    a, _, _ = andy(Thing("glasses", -50.0, 20.0), spark=spark, tmp_path=tmp_path)
    assert a.hear("where are my glasses, I think I left them by the TV").endswith("I see your glasses, to my right.")
    assert a.screen.source == "cloud" and len(a.screen.snapshot()["steps"]) == 2  # look, then look closer and point
    for req in spark.requests:  # nothing but text goes up
        assert all(isinstance(m.get("content"), str) for m in req["messages"])


def test_when_the_cloud_planner_fails_the_robot_searches_on_its_own(tmp_path):
    class Down:
        chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(
            CloudUnavailable("down", ["r1"]))))

    a, _, _ = andy(Thing("glasses", -48.0, 22.0), spark=Down(), tmp_path=tmp_path)
    assert a.hear("where are my glasses, I think I left them by the TV").endswith("I see your glasses, to my right.")
    assert a.screen.source == "device"


def test_web_questions_need_the_cloud(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path, online=False)
    assert "not connected" in a.hear("What's the weather tomorrow?")
    cite = SimpleNamespace(type="url_citation", url="https://www.weather.gov/x", title="Forecast")
    resp = SimpleNamespace(output_text="Sunny, with a high of 61.", usage=None,
                           output=[SimpleNamespace(content=[SimpleNamespace(annotations=[cite])])])
    spark = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: resp))
    a, _, _ = andy(spark=spark, tmp_path=tmp_path)
    assert a.hear("What's the weather tomorrow?").endswith("Sunny, with a high of 61. That's according to weather.gov.")
    assert a.screen.snapshot()["sources"] == [{"title": "Forecast", "url": "https://www.weather.gov/x"}]


def test_a_reminder_is_delivered_in_person(tmp_path):
    a, body, clock = andy(Thing("person", 0.0, -5.0, size_px=300), tmp_path=tmp_path)
    assert "remind you" in a.hear("remind me in 10 minutes to check the oven")
    clock.t += 9 * 60
    a.tick()
    assert not any("check the oven" in s for s in said(body)[1:])
    clock.t += 2 * 60
    a.tick()
    assert said(body)[-1].endswith("You asked me to remind you: check the oven")
    assert a.reminders.upcoming() == []


def test_a_missed_reminder_is_mentioned_next_time(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)  # nobody in the room
    a.hear("remind me in 10 minutes to check the oven")
    for minutes in (10, 15, 20):  # due, then two retries five minutes apart
        clock.t = T0 + minutes * 60 + 1
        a.tick()
    assert a.reminders.missed_unmentioned()
    a.hear("hello")
    assert any("couldn't find you to remind you: check the oven" in s for s in said(body))


@pytest.mark.parametrize("text, words", [
    ("what do you remember", "not keeping an eye on anything"),
    ("remind me", "What should I remind you about"),
    ("what are my reminders", "no reminders")])
def test_plain_answers(tmp_path, text, words):
    a, _, _ = andy(tmp_path=tmp_path)
    assert words in a.hear(text)


def test_offline_with_a_hint_glimmer_plans_the_search_on_this_computer(tmp_path):
    glimmer = ScriptedSpark(
        [("look", {"object": "glasses", "views": ["far right"]})],
        [("look_closer", {"object": "glasses", "place": "1"})],
        [("point", {"place": "1"})],
        "Found them, on your right.")
    a, _, _ = andy(Thing("glasses", -50.0, 20.0), online=False, tmp_path=tmp_path)
    a.glimmer = glimmer
    assert a.hear("where are my glasses, I had them by the TV on the right").endswith("I see your glasses, to my right.")
    assert a.screen.source == "device" and "Glimmer" in a.screen.reason
    assert glimmer.requests[0]["model"] == "muse-glimmer-30B"
    assert glimmer.requests[0]["messages"][0]["content"].startswith("Reasoning effort: low.")
    assert not (tmp_path / "logs").exists()  # nothing spent


def test_a_plain_request_gets_the_fast_sweep_even_with_planners(tmp_path):
    glimmer = ScriptedSpark()
    a, _, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.glimmer = glimmer
    assert a.hear("where are my keys").endswith("I see your keys, a little to my left.")
    assert glimmer.requests == []


def test_the_tv_shows_which_models_worked_on_a_turn(tmp_path):
    a, _, _ = andy(Thing("glasses", 52.0, 5.0, on_screen=True), Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.hear("where are my glasses")
    models = {m["name"]: (m["where"], m["times"]) for m in a.screen.snapshot()["models"]}
    assert models["SAM 3.1"][0] == "device" and models["SAM 3.1"][1] >= 3
    assert models["Muse Glimmer (picture check)"][0] == "device"
    a.hear("tell me a joke")
    assert [m["name"] for m in a.screen.snapshot()["models"]] == ["Muse Glimmer"]  # a new turn starts afresh


def test_what_i_remember_says_when_and_where(tmp_path):
    a, _, clock = andy(Thing("keys", 40.0, 20.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("where are my keys")
    clock.t += 2 * 3600 + 60
    a.hear("what do you remember")
    assert a.screen.snapshot()["memory"] == ["keys: seen 2 hours ago, to my left"]


def test_a_conversation_is_remembered_for_a_while_then_forgotten(tmp_path):
    a, _, clock = andy(tmp_path=tmp_path)
    a.hear("What's a good word for sunny?")
    a.hear("And for rainy?")
    assert a.device.history == [("What's a good word for sunny?", "Hello there.")]  # without the AI opening
    clock.t += 31 * 60
    a.hear("Hello again")
    assert a.device.history == []


def test_andys_question_takes_the_next_answer(tmp_path):
    a, _, clock = andy(tmp_path=tmp_path)
    assert "What should I remind you about" in a.hear("remind me to stretch")  # no time heard
    assert "remind you at" in a.hear("in two minutes to stretch")
    assert [r.text for r in a.reminders.upcoming()] == ["stretch"]


def test_until_minutes_is_in_two_minutes(tmp_path):
    a, _, clock = andy(tmp_path=tmp_path)
    a.hear("remind me until minutes to stretch")
    r = a.reminders.upcoming()[0]
    assert r.text == "stretch" and r.at - clock.t == pytest.approx(120, abs=1)


@pytest.mark.parametrize("model_said", ["Got it. I'll remind you to stretch in two minutes.",
                                        "I'm still keeping an eye on the cup. I will watch it for you.",
                                        "Sure, I'll look for your keys now."])
def test_the_chat_model_cannot_promise_what_it_cannot_do(tmp_path, model_said):
    a, _, _ = andy(tmp_path=tmp_path)
    a.device.text = model_said
    reply = a.hear("can you help me later")
    assert "Say it to me directly" in reply and "promise" in a.screen.reason
