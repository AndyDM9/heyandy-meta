import json

import pytest

from heyandy_meta.companion.attention import face_person
from heyandy_meta.companion.reminders import TRIES, Reminders, spoken_time
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing


def room_with_person(yaw=-40.0, pitch=8.0):
    room = Room([Thing("person", yaw, pitch, size_px=400)])
    return room, SimBody(room), SimSegmenter(room)


def test_turns_to_the_person_aiming_near_the_face():
    _, body, seg = room_with_person(-40.0, 8.0)
    yaw, pitch = face_person(body, seg)
    assert yaw == pytest.approx(-40.0, abs=1.0)
    assert pitch < 8.0  # higher than the middle of the person, towards the face
    assert (round(body.yaw, 1), round(body.pitch, 1)) == (round(yaw, 1), round(pitch, 1))


def test_looks_where_it_is_already_facing_first():
    room, body, seg = room_with_person(5.0, 10.0)
    body.look(0.0, 10.0)
    face_person(body, seg)
    assert seg.calls == 1


def test_nobody_there_means_none_and_no_guess():
    room = Room([Thing("keys", 10.0, 10.0)])
    assert face_person(SimBody(room), SimSegmenter(room)) is None


def test_spoken_time():
    import datetime as dt
    t = dt.datetime(2026, 11, 1, 15, 0).timestamp()
    assert spoken_time(t) == "3 o'clock"
    assert spoken_time(t + 5 * 60) == "3:05"


def test_reminder_is_said_in_person_with_the_persons_own_words(tmp_path):
    rs = Reminders(tmp_path / "r.json")
    r = rs.add("call Anna", at=2000.0, now=1000.0)
    assert rs.due(now=1999.0) == [] and rs.due(now=2000.0) == [r]
    said = []
    assert rs.deliver(r, find_person=lambda: (0, 0), say=said.append, now=2000.0) == "said"
    assert said[0].endswith("You asked me to remind you: call Anna")
    assert rs.due(now=9999.0) == []


def test_nobody_in_view_retries_then_lets_go_and_mentions_it_later(tmp_path):
    rs = Reminders(tmp_path / "r.json")
    r = rs.add("water the plants", at=2000.0, now=1000.0)
    outcomes = [rs.deliver(r, lambda: None, print, now=2000.0 + i * 300) for i in range(TRIES)]
    assert outcomes == ["retry", "retry", "missed"]
    said = []
    assert rs.mention_missed(said.append) == 1 and "couldn't find you" in said[0]
    assert rs.mention_missed(said.append) == 0  # only once


def test_daily_reminders_come_back_tomorrow(tmp_path):
    rs = Reminders(tmp_path / "r.json")
    r = rs.add("evening walk", at=2000.0, daily=True, now=1000.0)
    rs.deliver(r, lambda: (0, 0), lambda s: None, now=2000.0)
    assert r.state == "waiting" and r.at == 2000.0 + 86400


@pytest.mark.parametrize("text, at", [("", 2000.0), ("x" * 141, 2000.0), ("call Anna", 500.0)])
def test_bad_reminders_are_refused(tmp_path, text, at):
    with pytest.raises(ValueError):
        Reminders(tmp_path / "r.json").add(text, at, now=1000.0)


def test_the_file_holds_only_words_times_and_state(tmp_path):
    rs = Reminders(tmp_path / "r.json")
    rs.add("call Anna", at=2000.0, now=1000.0)
    saved = json.loads((tmp_path / "r.json").read_text())[0]
    assert set(saved) == {"id", "text", "at", "daily", "tries", "next_try", "state"}
    assert oct((tmp_path / "r.json").stat().st_mode)[-3:] == "600"
    assert Reminders(tmp_path / "r.json").upcoming()[0].text == "call Anna"
