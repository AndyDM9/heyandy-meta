import pytest

from heyandy_meta.companion.follow import follow
from heyandy_meta.companion.intents import parse
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing
from tests.test_app import andy


class MovingRoom:
    """The mug slides 6 degrees to the left each time the camera reads a frame."""

    def __init__(self, step=6.0):
        self.mug = Thing("mug", -20.0, 15.0)
        self.room = Room([self.mug])
        self.body = SimBody(self.room)
        capture = self.body.capture

        def moving_capture():
            frame = capture()
            self.mug.yaw += step
            return frame

        self.body.capture = moving_capture


def test_the_eyes_follow_a_moving_thing_until_told_to_stop():
    m = MovingRoom()
    m.body.look(-20.0, 15.0)
    frames = []
    why = follow(m.body, SimSegmenter(m.room), "mug", (-20.0, 15.0), lambda *a: frames.append(a[2]),
                 stop=lambda: len(frames) >= 8)
    assert why == "stopped" and len(frames) == 8
    assert frames == sorted(frames) and frames[-1] > 15  # it went left with the mug
    looks = [e for e in m.body.log if e[0] == "look"]
    assert looks[-1][1] == pytest.approx(frames[-1], abs=0.5)


def test_out_of_sight_for_a_while_means_lost():
    m = MovingRoom()
    m.room.things.clear()
    assert follow(m.body, SimSegmenter(m.room), "mug", (0.0, 15.0), lambda *a: None, stop=lambda: False) == "lost"


def test_the_nearest_of_two_look_alikes_stays_the_same_one():
    room = Room([Thing("mug", -10.0, 15.0), Thing("mug", 25.0, 15.0)])
    body = SimBody(room)
    body.look(-10.0, 15.0)
    seen = []
    follow(body, SimSegmenter(room), "mug", (-10.0, 15.0), lambda f, m, y, p: seen.append(y), stop=lambda: len(seen) >= 3)
    assert all(y == pytest.approx(-10.0, abs=0.5) for y in seen)


def test_follow_the_mug_is_a_request_to_follow():
    assert (parse("Andy, follow the mug").kind, parse("Andy, follow the mug").thing) == ("follow", "mug")
    assert parse("track my phone please").thing == "phone"
    assert parse("keep an eye on my keys").kind == "watch"  # remembering, not following


def test_andy_follows_then_says_so(tmp_path):
    a, body, _ = andy(Thing("keys", 20.0, 20.0), tmp_path=tmp_path)
    reply = a.follow("keys", seconds=0.05)
    assert reply.startswith("That's enough following") and not a.following
    assert any("Following your keys" in e[1] for e in body.log if e[0] == "say")


def test_follow_what_isnt_there_says_so(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "couldn't find your keys" in a.follow("keys", seconds=0.05)
