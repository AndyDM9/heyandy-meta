import math
import struct
from types import SimpleNamespace

import pytest

from heyandy_meta.finder.search import Finder
from heyandy_meta.robot.body import Reach
from heyandy_meta.robot.reachy_mini import ReachyBody, jpeg_size


def tiny_jpeg(w=1920, h=1080):
    """Just enough JPEG for the size reader: SOI, an APP0 segment, and a baseline frame header."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, h, w, 3) + b"\x00" * 9
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


class FakeReachy:
    def __init__(self):
        self.moves = []
        self.media = SimpleNamespace(get_frame_jpeg=lambda: tiny_jpeg())

    def goto_target(self, head=None, body_yaw=None, duration=0.5, **kw):
        self.moves.append((head, body_yaw, duration))


class SaggingReachy(FakeReachy):
    """Like the Lite measured on 2026-10-27: the head reaches three quarters of a yaw and sags 3 degrees; the base is exact."""

    def get_current_head_pose(self):
        _, yaw, pitch = self.moves[-1][0]
        y, p = math.radians(yaw * 0.75), math.radians(pitch + 3.0)
        return [[math.cos(y) * math.cos(p), -math.sin(y), 0, 0], [math.sin(y) * math.cos(p), math.cos(y), 0, 0],
                [-math.sin(p), 0, math.cos(p), 0], [0, 0, 0, 1]]

    def get_current_joint_positions(self):
        return [self.moves[-1][1]] + [0.0] * 6, [0.0, 0.0]


def body(robot=None, **kw):
    robot = robot or FakeReachy()
    return ReachyBody(robot, pose=lambda yaw, pitch, roll=0.0: ("pose", round(yaw, 2), round(pitch, 2)), sleep=lambda s: None,
                      **kw), robot


def test_jpeg_size():
    assert jpeg_size(tiny_jpeg(1280, 720)) == (1280, 720)
    with pytest.raises(ValueError):
        jpeg_size(b"\x89PNG not a jpeg")


def test_small_turns_are_the_head_alone():
    b, robot = body()
    b.look(25.0, 15.0)
    head, base, duration = robot.moves[-1]
    assert head == ("pose", 25.0, 15.0) and base == 0.0 and duration == pytest.approx(0.6)


def test_past_the_head_the_base_makes_up_the_rest():
    b, robot = body()
    b.look(74.0, 20.0)
    head, base, _ = robot.moves[-1]
    assert head == ("pose", 30.0, 20.0)
    assert math.degrees(base) == pytest.approx(44.0)


def test_directions_are_clamped_and_moves_stay_gentle():
    b, robot = body(reach=Reach(yaw=60.0, pitch_down=30.0))
    b.look(-170.0, 80.0)
    head, base, duration = robot.moves[-1]
    assert head == ("pose", -30.0, 30.0) and math.degrees(base) == pytest.approx(-30.0)
    assert duration == pytest.approx(60.0 / 70.0)  # 60 degrees at 70 degrees a second


def test_a_sagging_head_is_measured_and_corrected_once():
    b, robot = body(SaggingReachy())
    b.look(20.0, 10.0)
    assert len(robot.moves) == 2  # the move, then one correction
    assert robot.moves[1][0][1] > 20.0 and robot.moves[1][0][2] < 10.0  # aim past the shortfall, above the sag
    assert abs(b.yaw - 20.0) < 1.5 and abs(b.pitch - 10.0) < 1.5
    f = b.capture()
    assert (f.yaw, f.pitch) == (b.yaw, b.pitch)  # the frame carries where the head really was


def test_the_base_is_trusted_and_only_the_head_is_corrected():
    b, robot = body(SaggingReachy())
    b.look(70.0, 15.0)
    bases = [round(math.degrees(m[1]), 3) for m in robot.moves]
    assert bases == [40.0, 40.0]


def test_capture_reports_where_the_head_was():
    b, _ = body()
    b.look(-18.0, 15.0)
    f = b.capture()
    assert (f.width, f.height, f.yaw, f.pitch) == (1920, 1080, -18.0, 15.0)


def test_point_faces_then_dips_once_and_holds():
    b, robot = body()
    b.point(20.0, 10.0)
    heads = [m[0] for m in robot.moves]
    assert heads == [("pose", 20.0, 10.0), ("pose", 20.0, 16.0), ("pose", 20.0, 10.0)]  # no read-back: no correction


def test_the_finder_drives_the_adapter_like_any_body():
    b, robot = body()

    class Nothing:
        def find(self, frame, query):
            return []

    assert Finder(b, Nothing()).find("glasses") is None
    assert [m[0][1] for m in robot.moves] == [18.0, -18.0, 30.0, -30.0, 30.0, -30.0]  # the base makes up the rest


@pytest.mark.parametrize("name", ["listening", "thinking", "found", "nod"])
def test_gestures_never_swing_the_base_back(name):
    b, robot = body()
    b.look(100.0, 10.0)
    b.gesture(name)
    assert all(math.degrees(m[1]) == pytest.approx(70.0) for m in robot.moves)  # the base stays turned
