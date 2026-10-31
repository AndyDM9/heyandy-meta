import numpy as np
import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.sound import (AHEAD_DEG, NARROW_DEG, RATE, Ear, fan, flatness, reading, ringing,
                                          turn_to)
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy, said

T = np.arange(1600) / RATE  # one chunk, 0.1 s


def tone():
    return 0.3 * (np.sin(2 * np.pi * 1400 * T) + np.sin(2 * np.pi * 1750 * T))


def test_a_ringtone_is_tonal_and_noise_is_not():
    """A steady hum is tonal too: what tells a voice apart is that only some of its chunks are (the share rule, below;
    on the robot a spoken sentence was never taken for a ringing)."""
    rng = np.random.default_rng(1)
    assert flatness(tone()) < 0.015
    assert flatness(rng.normal(0, 0.3, 1600)) > 0.5


def chunk(t, loud, flat, side):
    return (t, loud, flat, side)


def test_ringing_is_loud_mostly_tonal_and_has_a_side():
    floor = 0.01
    rings = [chunk(i, 0.2, 0.002, 30.0) for i in range(6)]
    assert reading(rings, floor) == 30.0
    talk = [chunk(i, 0.2, 0.05, 10.0) for i in range(8)] + [chunk(9, 0.2, 0.004, 10.0)] * 4  # a voice: tonal only now and then
    assert ringing(talk, floor) == []
    quiet = [chunk(i, 0.02, 0.002, 30.0) for i in range(8)]  # tonal but no louder than the room
    assert reading(quiet, floor) is None
    no_side = [chunk(i, 0.2, 0.002, None) for i in range(8)]
    assert reading(no_side, floor) is None


def test_the_ear_keeps_numbers_for_twenty_seconds_and_the_side_from_where_the_head_looks():
    t, head = [0.0], [20.0]
    ear = Ear(head=lambda: head[0], clock=lambda: t[0])
    ear(tone(), True, 35.0)  # the array says 35 degrees: 15 left of where the head looks
    ear(tone(), False, None)
    assert [c[3] for c in ear.since(0.0)] == [15.0, None]
    t[0] = 25.0
    ear(np.zeros(1600), False, None)
    assert len(ear.since(0.0)) == 1  # older than 20 s: gone


def compressed(source):
    """The array as measured on the robot: the side right, the size squeezed, near zero within 15 degrees."""
    def read(head):
        d = source - head
        return 0.0 if abs(d) < 15 else 0.3 * d
    return read


@pytest.mark.parametrize("source", [-60.0, -10.0, 25.0, 80.0])
@pytest.mark.parametrize("start", [-50.0, 0.0, 50.0])
def test_turning_by_the_side_heard_faces_the_sound_from_any_start(source, start):
    head = [start]
    read = compressed(source)
    yaw, steps = turn_to(lambda: read(head[0]), lambda y: head.__setitem__(0, y), start)
    assert abs(yaw - source) <= NARROW_DEG  # between the nearest clear left and clear right: the blind band's middle
    assert len(steps) <= 8


def test_no_ringing_no_turn():
    assert turn_to(lambda: None, lambda y: None, 0.0) == (None, [])


def test_the_fan_looks_that_way_low_and_high_then_either_side():
    views = fan(30.0)
    assert views[0] == (30.0, 20.0) and {v[0] for v in views} == {30.0, 52.0, 8.0}


class FakeEar:
    """The robot's ear, scripted: a phone ringing at one yaw, heard as the compressed array hears it."""

    def __init__(self, body, source):
        self.body, self.source, self.t = body, source, 0.0

    def clock(self):
        return self.t

    def floor(self):
        return 0.01

    def since(self, t):
        side = compressed(self.source)(self.body.yaw) if self.source is not None else None
        return [] if side is None else [(t + i * 0.1, 0.2, 0.002, side) for i in range(8)]


def test_andy_turns_to_the_ringing_and_finds_the_phone_there(tmp_path):
    a, body, clock = andy(Thing("phone", 40.0, 22.0), Thing("phone", -70.0, 22.0), tmp_path=tmp_path)
    a.ear, a.wait = FakeEar(body, 40.0), lambda s: None
    words = a.hear("Andy, I'm ringing my phone")
    assert "Ring it now, and I'll turn to the sound." in said(body)
    assert "I followed the ringing." in words and "phone" in words
    points = [e for e in body.log if e[0] == "point"]
    assert points and abs(points[-1][1] - 40.0) < 5  # the ringing one, not the silent one on the other side
    assert "Let me look." not in said(body)


def test_it_points_at_a_ringing_it_cant_see_and_says_so(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    a.ear, a.wait = FakeEar(body, -30.0), lambda s: None
    words = a.hear("I'm ringing my phone")
    assert "I can hear it, but I can't see it. It's ringing" in words and "under something" in words
    assert a.lost.looking() == []  # a search of its own: no promise made in passing
    yaw = [e for e in body.log if e[0] == "point"][-1][1]
    assert abs(yaw + 30.0) <= 15 + NARROW_DEG


def test_no_ringing_heard_and_no_microphones(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    assert "robot's microphones" in a.hear("I'm ringing my phone")
    a.ear, a.wait = FakeEar(body, None), lambda s: None
    assert "I didn't hear it ring." in a.hear("I'm ringing my phone")


def test_a_phone_not_found_suggests_ringing_it_on_the_robot(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "ringing" not in a.hear("where is my phone")  # no microphones: no such hint
    b, body, _ = andy(tmp_path=tmp_path / "b")
    b.ear = FakeEar(body, None)
    assert "If you can ring it, say: I'm ringing my phone." in b.hear("where is my phone")
    assert "If it has a tracker that beeps, say: listen for my keys." in b.hear("where are my keys")


@pytest.mark.parametrize("text, thing", [("Andy, I'm ringing my phone", "phone"), ("I am calling my cell", "phone"),
                                         ("listen for my keys", "keys"), ("find my phone by its sound", "phone"),
                                         ("I'm playing the sound on my keys", "keys"), ("estoy llamando a mi teléfono", "phone")])
def test_find_by_sound_is_asked_for_in_plain_words(text, thing):
    i = parse(text)
    assert i.kind == "sound" and i.thing == thing


def test_the_tv_shows_each_turn_and_where_it_faces():
    s = ScreenState()
    s.listening("phone", [(-50.0, 41.0), (-10.0, -2.0)], None)
    snap = s.snapshot()["sound"]
    assert snap["steps"] == [[-50.0, 41.0], [-10.0, -2.0]] and snap["facing"] is None and not snap["done"]
    s.listening("phone", [(-50.0, 41.0)], -12.5, done=True)
    assert s.snapshot()["sound"]["facing"] == -12.5
    s.clear()
    assert s.snapshot()["sound"] is None


def test_by_its_sound_a_thing_far_from_the_ringing_is_turned_down(tmp_path):
    a, body, _ = andy(Thing("phone", -45.0, 22.0), tmp_path=tmp_path)  # silent, well away from where it rings
    a.ear, a.wait = FakeEar(body, 10.0), lambda s: None
    words = a.hear("I'm ringing my phone")
    assert "I can hear it, but I can't see it." in words and a.finder.last_found is None


def test_andy_waits_for_the_ringing_to_start_while_the_person_dials():
    from heyandy_meta.companion.sound import wait_for

    heard = iter([None] * 7 + [12.0])  # about 11 seconds of dialling, then it rings
    assert wait_for(lambda: next(heard)) is True
    assert wait_for(lambda: None, seconds=8.0) is False  # never rings: gives up after the wait


def test_a_slow_dial_still_gets_turned_to(tmp_path):
    a, body, _ = andy(Thing("phone", 40.0, 22.0), tmp_path=tmp_path)
    ear = FakeEar(body, 40.0)
    calls = {"n": 0}
    real = ear.since

    def dialling(t):
        calls["n"] += 1
        return [] if calls["n"] <= 6 else real(t)  # silence while the person finds another phone and dials

    ear.since = dialling
    a.ear, a.wait = ear, lambda s: None
    assert "I followed the ringing." in a.hear("I'm ringing my phone")
