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


def test_andy_starts_with_a_remembered_distance(tmp_path):
    """On the robot (2026-10-31): a watched thing with its distance saved, and Andy failed to start."""
    places = Places(tmp_path / "places.json")
    places.watch("keys")
    places.saw("keys", -20.0, 15.0, when=0.0, metres=0.62)
    a, _, _ = andy(tmp_path=tmp_path)
    assert "about 2 feet away" in " ".join(str(x) for x in (a.screen.memory or a._memory()))


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
    assert reply.endswith("I see your glasses, to my right. Not the picture of one on the screen.")
    snap = a.screen.snapshot()
    assert snap["picture"] is None and snap["running"] is False  # the pretend room has no camera picture to show
    assert snap["source"] == "device" and any("looked" in s for s in snap["steps"])


def test_a_watched_thing_is_found_where_it_was_last_seen(tmp_path):
    a, body, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("where are my keys")
    body.log.clear()
    assert a.hear("where are my keys").endswith("Right where I last saw them.")
    assert [e[0] for e in body.log if e[0] in ("look", "capture")] == ["look", "capture", "look", "capture"]
    # one look straight at the remembered place, then the point (a look) and its check: no sweep


def test_the_cloud_plans_the_search_with_words_only(tmp_path):
    spark = ScriptedSpark(
        [("look", {"object": "glasses", "views": ["far right"]})],
        [("look_closer", {"object": "glasses", "place": "1"})],
        [("point", {"place": "1"})],
        "There they are, on your right.")
    a, _, _ = andy(Thing("glasses", -50.0, 20.0), spark=spark, tmp_path=tmp_path)
    assert a.hear("where are my glasses, I think I left them by the TV").endswith("I see your glasses, to my right.")
    steps = a.screen.snapshot()["steps"]  # look, then look closer and point, then the check after pointing
    assert a.screen.source == "cloud" and len(steps) == 3 and steps[-1].startswith("checked: pointing at it")
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
    assert not any("You asked me to remind you" in s for s in said(body))
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
    assert a.screen.snapshot()["memory"] == ["keys: seen 2 hours ago, on its own"]  # the place's words


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


def test_after_pointing_andy_turns_to_the_person_to_speak(tmp_path):
    a, body, _ = andy(Thing("keys", -40.0, 20.0), tmp_path=tmp_path)
    a.person = (10.0, -5.0)
    a.hear("where are my keys")
    moves = [e for e in body.log if e[0] in ("point", "look", "say")]
    i_point = max(i for i, e in enumerate(moves) if e[0] == "point")
    i_face = next(i for i, e in enumerate(moves) if i > i_point and e[0] == "look")
    i_say = next(i for i, e in enumerate(moves) if i > i_point and e[0] == "say")
    assert i_face < i_say and moves[i_face][1:] == (10.0, -5.0)


def test_upward_looks_at_a_face_are_softened():
    from heyandy_meta.companion.attention import soften_look_up

    assert soften_look_up(10.0) == 10.0  # down: as it is
    assert soften_look_up(-10.0) == pytest.approx(-6.0)
    assert soften_look_up(-40.0) == -12.0  # never more than 12 degrees up


def test_the_screen_shows_what_andy_is_doing_and_the_side_cards(tmp_path):
    a, _, clock = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("remind me in ten minutes to check the oven")
    snap = a.screen.snapshot()
    assert snap["next"]["text"] == "check the oven" and snap["watching"] == ["keys: not seen yet"]
    a.hear("where are my keys")
    snap = a.screen.snapshot()
    assert snap["looking_for"] == "keys" and snap["state"] == "Pointing" and snap["head"] == "At your keys"
    assert snap["watching"][0].startswith("keys: seen just now")
    a.hear("tell me a joke")
    assert a.screen.snapshot()["state"] == "Waiting"


def test_what_can_i_ask_opens_the_guide(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "ideas on the screen" in a.hear("what can I ask you?")
    assert a.screen.snapshot()["help"] is True


def test_a_staged_scene_sends_the_finders_frames_to_the_api_and_says_so(tmp_path):
    a, _, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    local = a.segmenter
    api = SimSegmenter(Room([Thing("keys", 20.0, 20.0)]))
    a.use_staged_scene(api)
    a.hear("where are my keys")
    assert api.calls > 0 and a.segmenter is local  # only the finder; the glance and the face tracker stay local
    snap = a.screen.snapshot()
    assert snap["staged"] is True and {m["name"]: m["where"] for m in snap["models"]}["SAM 3.1"] == "cloud"


@pytest.mark.parametrize("said, place", [("Andy, what am I holding?", ""), ("what's on the table?", "table"),
                                         ("what is this", ""), ("what do you see", "")])
def test_what_am_i_holding_is_a_request_to_look_and_tell(said, place):
    from heyandy_meta.companion.intents import parse

    i = parse(said)
    assert (i.kind, i.thing) == ("describe", place)


def test_andy_looks_and_says_what_it_sees(tmp_path):
    a, body, _ = andy(Thing("mug", 0.0, 28.0), tmp_path=tmp_path)
    assert a.hear("what's on the table?").endswith("I see a mug.")
    assert ("look", 0.0, 28.0) in body.log  # it looked down at the table
    assert {m["name"]: m["where"] for m in a.screen.snapshot()["models"]}["Muse Glimmer (looks)"] == "device"


@pytest.mark.parametrize("said, what", [("speak up please", "louder"), ("Andy, I can't hear you", "louder"),
                                        ("that's too loud", "quieter"), ("speak more slowly", "slower"),
                                        ("a bit faster please", "faster"), ("what did you say?", "repeat"),
                                        ("say that again", "repeat")])
def test_how_andy_speaks_is_asked_for_by_voice(said, what):
    from heyandy_meta.companion.intents import parse

    i = parse(said)
    assert (i.kind, i.thing) == ("voice", what)


def test_say_that_again_and_speak_up_are_remembered(tmp_path):
    from types import SimpleNamespace as NS

    a, _, _ = andy(tmp_path=tmp_path)
    a.voice = NS(speed=1.0, loudness=-21.0)
    a.hear("tell me a joke")
    assert a.hear("what did you say?") == "Hello there."
    assert a.hear("speak up") == "Is this better?" and a.voice.loudness == -18.0
    assert a.hear("say that again") == "Hello there."  # still the last real answer, not "Is this better?"
    for _ in range(5):
        a.hear("speak more slowly")
    assert a.voice.speed == 0.7 and a.hear("slower") == "That's as slowly as I speak."
    b, _, _ = andy(tmp_path=tmp_path)
    b.voice = NS(speed=1.0, loudness=-21.0)
    b.load_voice()
    assert (b.voice.speed, b.voice.loudness) == (0.7, -18.0)


def test_a_voice_change_shows_briefly_on_the_tv(tmp_path):
    from types import SimpleNamespace as NS

    a, _, _ = andy(tmp_path=tmp_path)
    a.voice = NS(speed=1.0, loudness=-21.0)
    a.hear("speak up")
    assert a.screen.snapshot()["notice"] == "Volume ●●●●●○○ · Speed ●●●●○○○"
    a.screen._clock = lambda: 10 ** 12  # much later
    assert a.screen.snapshot()["notice"] == ""


def test_quiet_time_means_no_glances_and_reminders_without_searching(tmp_path):
    a, body, clock = andy(Thing("person", 0.0, -5.0, size_px=300), Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("remind me in ten minutes to check the oven")
    assert "keep quiet until" in a.hear("Andy, be quiet for an hour")
    assert a.screen.snapshot()["quiet"].startswith("Quiet until")
    body.log.clear()
    clock.t += 11 * 60
    a.tick()
    assert not [e for e in body.log if e[0] in ("look", "capture")]  # no glance, no search for the person
    assert any("check the oven" in e[1] for e in body.log if e[0] == "say")  # but the reminder was said
    clock.t += 60 * 60
    a.tick()
    assert a.screen.snapshot()["quiet"] == "" and not a.quiet()


def test_quiet_can_end_early_and_motion_is_remembered(tmp_path):
    from heyandy_meta.companion.intents import parse

    assert parse("Andy, do not disturb me for 30 minutes").at == 1800
    a, _, _ = andy(tmp_path=tmp_path)
    a.hear("be quiet")
    assert a.hear("you can talk again") == "Okay, I'm back to normal." and not a.quiet()
    assert a.hear("move less") == "Like this?" and a.liveliness == 0.65
    b, _, _ = andy(tmp_path=tmp_path)
    b.load_voice()
    assert b.liveliness == 0.65


def test_the_privacy_receipt_says_what_left_the_house(tmp_path):
    from types import SimpleNamespace as NS

    a, _, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    a.hear("where are my keys")
    assert a.screen.snapshot()["outbox"] == []  # found on this computer: nothing sent
    cite = NS(type="url_citation", url="https://www.weather.gov/x", title="Forecast")
    resp = NS(output_text="Sunny.", usage=None, output=[NS(content=[NS(annotations=[cite])])])
    b, _, _ = andy(spark=NS(responses=NS(create=lambda **kw: resp)), tmp_path=tmp_path / "b")
    b.home = "Sunny Isles Beach, Florida"
    b.hear("what's the weather tomorrow?")
    sent = b.screen.snapshot()["outbox"]
    assert sent == [{"to": "Muse Spark + web search", "earlier": 0,
                     "words": "(home: Sunny Isles Beach, Florida) what's the weather tomorrow?"}]  # the home first: never cut


def test_when_did_you_last_see_my_keys_answers_from_memory_with_what_it_was_near(tmp_path):
    keys = Thing("keys", 30.0, 20.0)
    a, body, clock = andy(keys, Thing("mug", 38.0, 18.0), tmp_path=tmp_path)
    a.hear("keep an eye on my keys")
    a.hear("where are my keys")
    clock.t += 40 * 60
    keys.yaw = -35.0  # someone moved them
    a.hear("where are my keys")
    clock.t += 10 * 60
    body.log.clear()
    reply = a.hear("Andy, when did you last see my keys?")
    assert reply.startswith("I last saw your keys 10 minutes ago, on its own.")
    assert "Before that, next to the mug, until" in reply
    assert not [e for e in body.log if e[0] in ("look", "capture")]  # from memory: the robot didn't move
    assert "(moved at" in a.screen.snapshot()["memory"][0]


def test_where_did_i_leave_something_not_watched_looks_for_it(tmp_path):
    a, _, _ = andy(Thing("wallet", -20.0, 20.0), tmp_path=tmp_path)
    assert a.hear("where did I leave my wallet?").endswith("I see your wallet, a little to my right.")


def test_asked_three_times_this_week_andy_offers_to_keep_an_eye(tmp_path):
    a, body, clock = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    for _ in range(2):
        assert "keep an eye" not in a.hear("where are my glasses?")
        clock.t += 3600
    assert "asked me about your glasses 3 times this week. Shall I keep an eye on them?" in a.hear("where are my glasses?")
    assert "I'll keep an eye on your glasses" in a.hear("yes please") and "glasses" in a.places.watching()


def test_no_thanks_and_once_a_week(tmp_path):
    a, body, clock = andy(Thing("keys", 30.0, 25.0), tmp_path=tmp_path)
    for _ in range(3):
        clock.t += 600
        reply = a.hear("where are my keys?")
    assert "Shall I keep an eye" in reply
    assert "Just ask me" in a.hear("no thanks") and a.places.watching() == []
    clock.t += 600
    assert "Shall I keep an eye" not in a.hear("where are my keys?")  # offered once this week


def test_no_but_a_new_request_is_answered(tmp_path):
    a, body, clock = andy(Thing("glasses", -48.0, 22.0), Thing("keys", 30.0, 25.0), tmp_path=tmp_path)
    for _ in range(3):
        clock.t += 600
        reply = a.hear("where are my glasses?")
    assert "Shall I keep an eye" in reply
    assert "keys" in a.hear("No, where are my keys?")


def test_yes_keeps_the_place_it_was_just_found(tmp_path):
    a, body, clock = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    for _ in range(3):
        clock.t += 600
        a.hear("where are my glasses?")
    a.hear("yes, please do")
    assert a.places.last_seen("glasses", now=clock()) is not None


def test_the_receipt_lists_earlier_exchanges_word_for_word_and_counts_a_failed_attempt(tmp_path):
    from heyandy_meta.models.retry import CloudUnavailable

    class Down:
        def chat(self, prompt, history=()):
            raise CloudUnavailable("down", [])

    a, _, _ = andy(tmp_path=tmp_path)
    a.router.cloud = Down()
    a.hear("my neighbour's door code is 4512")
    a.hear("explain why the sky is blue, in detail please, and how sunsets get their colours")
    sent = a.screen.snapshot()["outbox"]
    assert sent[0]["to"] == "Muse Spark" and "sky is blue" in sent[0]["words"]  # recorded although the cloud failed
    assert any("door code is 4512" in o["words"] for o in sent[1:])  # the history that went with it, in words


def test_a_staged_scene_says_camera_pictures_went(tmp_path):
    a, _, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    a.vision_where = "cloud"
    a.hear("where are my keys")
    assert any(o.get("pictures") and "camera pictures" in o["words"] for o in a.screen.snapshot()["outbox"])


def emotes(body):
    return [e[1] for e in body.log if e[0] == "emote"]


def test_andy_shows_a_feeling_at_calm_moments_only(tmp_path):
    a, body, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.hear("Thank you, Andy")
    a.hear("where are my glasses")  # not here: an "oops", after the search, not during it
    assert emotes(body) == ["grateful1", "oops1"]
    body.log.clear()
    a.hear("where are my keys")
    assert emotes(body) == []  # found and pointing: the head stays on the thing


def test_no_feelings_in_a_crisis_or_when_asked_to_move_less(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    a.hear("Thank you. I want to die")
    assert emotes(body) == []
    a.hear("move less")
    a.hear("move less")
    a.hear("thank you")
    assert emotes(body) == []


@pytest.mark.parametrize("asked, answer", [("Andy, what time is it?", "It's 9:54."), ("whats the time", "It's 9:54."),
                                           ("What day is it today?", "It's Saturday, October 31."),
                                           ("what's the date", "It's Saturday, October 31.")])
def test_the_time_and_the_day_come_from_the_clock(tmp_path, asked, answer):
    """Glimmer isn't told the time and would guess; the clock says it."""
    import datetime as dt

    a, _, clock = andy(tmp_path=tmp_path)
    clock.t = dt.datetime(2026, 10, 31, 9, 54).timestamp()
    assert a.hear(asked).endswith(answer)
