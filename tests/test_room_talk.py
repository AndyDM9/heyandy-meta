"""A conversation Andy isn't part of, replayed through its listening (evals/room_talk.py): only times are read."""
from types import SimpleNamespace

from evals import room_talk


def test_only_times_and_answered_or_not_are_read_from_the_journal():
    journal = ("1762100000.100000 host python[1]: (heard 2.1s of speech, room level 0.004; not for Andy)\n"
               "1762100009.500000 host python[1]: turn answered [first word 2.4s after the person stopped]\n"
               "1762100012.000000 host python[1]: watching my microphones and speaker\n")
    run = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=journal, stderr="")  # noqa: E731
    assert room_talk.timeline(0, 1, run=run) == [(1762100000.1, False), (1762100009.5, True)]


def test_the_first_answer_after_a_quiet_spell_is_the_call_and_answers_are_said_a_turn_earlier():
    rows = [(0.0, False), (100.0, True), (115.0, True), (200.0, True)]
    said = room_talk.utterances(rows, turn_s=6.0, gap_s=30.0)
    assert said == [(0.0, room_talk.TALK), (94.0, room_talk.CALL), (109.0, room_talk.TALK), (194.0, room_talk.CALL)]


def meeting(minutes=20, every_s=5.0, called_at=(300.0,)):
    said = [(i * every_s, room_talk.TALK) for i in range(int(minutes * 60 / every_s))]
    return sorted(said + [(t + 0.5, room_talk.CALL) for t in called_at])


def test_a_meeting_kept_andy_answering_before_and_doesnt_now():
    before = room_talk.replay(meeting(), turn_s=6.0, **room_talk.OLD)
    now = room_talk.replay(meeting(), turn_s=6.0)
    assert before["answered"] > 50 and before["called by name"] == 1
    assert now["answered"] <= 2 and now["most in ten minutes"] <= 2


def test_a_conversation_in_a_quiet_room_keeps_its_follow_ups():
    assert room_talk.conversation(then=6)["answered without the name"] == 6
    assert room_talk.conversation(then=8)["answered without the name"] == 6  # then the name again
