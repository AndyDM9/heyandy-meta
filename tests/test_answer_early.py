import time

from heyandy_meta.robot.sim import Thing
from tests.test_app import andy, said


def test_the_answer_starts_while_the_head_points_and_the_turn_waits_for_both(tmp_path):
    a, body, _ = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.answer_while_pointing = True  # as on the robot
    marks = {}
    point, say, chime = body.point, body.say, body.chime

    def slow_point(yaw, pitch):
        time.sleep(0.3)  # the head takes a while to turn, dip and settle
        point(yaw, pitch)
        marks["pointed"] = time.monotonic()

    def timed_say(text):
        marks.setdefault("said", time.monotonic())
        say(text)

    def timed_chime(name):
        marks.setdefault(name, time.monotonic())
        chime(name)

    body.point, body.say, body.chime = slow_point, timed_say, timed_chime
    words = a.hear("where are my keys?")
    assert "There they are!" in words or "Found them!" in words or "keys" in words
    assert marks["found"] < marks["pointed"] and marks["said"] < marks["pointed"]  # the note and the words came first
    answer = [w for w in said(body) if "your keys" in w]
    assert len(answer) == 1  # said once, while pointing; not again at the end of the turn
    assert a._early is None  # the turn waited for the answer, and let it go


def test_a_search_of_andys_own_never_answers_early(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.answer_while_pointing = True
    a.hear("where is my wallet")  # missed: Andy keeps looking
    body.room.things.append(Thing("wallet", 30.0, 20.0))
    clock.t += 3 * 60
    body.log.clear()
    a.tick()  # the look-again: its own words ("Good news ..."), not the plain answer
    spoken = said(body)
    assert spoken and spoken[-1].startswith("Good news: your wallet turned up!")
    assert not any(w.startswith("There it is") or w.startswith("Found it") for w in spoken)
