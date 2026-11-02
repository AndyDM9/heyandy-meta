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
        self.media = SimpleNamespace(get_frame_jpeg=lambda: tiny_jpeg(), start_playing=lambda: None,
                                     push_audio_sample=lambda s: None)

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
    assert head == ("pose", 74.0, 20.0)  # the daemon takes the head's direction in the room, the base's turn in it
    assert math.degrees(base) == pytest.approx(44.0)  # the head turns 30 on the body, the base the other 44


def test_directions_are_clamped_and_moves_stay_gentle():
    b, robot = body(reach=Reach(yaw=60.0, pitch_down=30.0))
    b.look(-170.0, 80.0)
    head, base, duration = robot.moves[-1]
    assert head == ("pose", -60.0, 30.0) and math.degrees(base) == pytest.approx(-30.0)
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


class ExactReachy(FakeReachy):
    """Like the daemon: the head pose read back is the head's direction in the room, the base's turn already in it."""

    def get_current_head_pose(self):
        _, yaw, pitch = self.moves[-1][0]
        y, p = math.radians(yaw), math.radians(pitch)
        return [[math.cos(y) * math.cos(p), -math.sin(y), 0, 0], [math.sin(y) * math.cos(p), math.cos(y), 0, 0],
                [-math.sin(p), 0, math.cos(p), 0], [0, 0, 0, 1]]

    def get_current_joint_positions(self):
        return [self.moves[-1][1]] + [0.0] * 6, [0.0, 0.0]


def test_the_head_pose_is_read_in_the_rooms_frame():
    """Found on the Lite, 2026-10-31: adding the base's turn to the head pose counted it twice, so past 30 degrees
    Andy thought it faced twice as far round as it did, and never really looked past 30 degrees."""
    b, robot = body(ExactReachy())
    b.look(70.0, 15.0)
    assert len(robot.moves) == 1  # it is where it was sent: no correction
    assert (round(b.yaw, 6), round(b.pitch, 6)) == (70.0, 15.0)


def test_capture_reports_where_the_head_was():
    b, _ = body()
    b.look(-18.0, 15.0)
    f = b.capture()
    assert (f.width, f.height, f.yaw, f.pitch) == (1920, 1080, -18.0, 15.0)


class Clock:
    """Time that passes only when the body sleeps: what each capture waited, and when."""

    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.now += s


def test_a_frame_is_taken_only_once_the_picture_has_caught_up_with_the_head():
    """Measured on the Lite, November 1: the head stops about 0.15 s after a move, but its frames go on sharpening
    until about 0.35 to 0.45 s. The frame must come at least ``fresh_s`` after the move, the look's own settling
    counted; a head still for a while waits for nothing."""
    clock = Clock()
    robot = FakeReachy()
    b = ReachyBody(robot, pose=lambda yaw, pitch, roll=0.0: ("pose", yaw, pitch), sleep=clock.sleep, clock=clock)
    b.look(-18.0, 15.0)  # sleeps settle_s (0.3) itself
    moved = clock.now - 0.3
    b.capture()
    assert clock.now - moved == pytest.approx(b.fresh_s)  # 0.3 settling, then the rest: fresh_s after the move
    before = len(clock.slept)
    clock.now += 5.0  # the head has been still a while (the hand-guiding's frames, say)
    b.capture()
    assert len(clock.slept) == before  # nothing to wait for


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
    assert [m[0][1] for m in robot.moves] == [18.0, -18.0, 55.0, -55.0, 110.0, -110.0]  # the room's directions
    assert [round(math.degrees(m[1])) for m in robot.moves] == [0, 0, 25, -25, 80, -80]  # the base makes up the rest


@pytest.mark.parametrize("name", ["listening", "thinking", "found", "nod", "searching", "idle"])
def test_gestures_never_swing_the_base_back(name):
    b, robot = body()
    b.look(100.0, 10.0)
    b.gesture(name)
    assert all(math.degrees(m[1]) == pytest.approx(70.0) for m in robot.moves)  # the base stays turned


def test_gestures_set_the_body_language_mode():
    b, _ = body()
    b.gesture("listening")
    assert b.motion.mode == "listening"
    b.play([0.0] * 160)
    assert b.motion.mode == "idle"  # after speaking, back to idle


def test_facing_eases_the_head_within_its_range():
    b, _ = body()
    b.look(0.0, 10.0)
    b.face(20.0, 5.0)
    for _ in range(100):
        b._ease(0.02)
    assert b._sent[0] == pytest.approx(20.0) and b._sent[1] == pytest.approx(5.0)
    b.face(80.0, 5.0)
    for _ in range(100):
        b._ease(0.02)
    assert b._sent[0] == pytest.approx(30.0)  # the head's share; turning further is a move of its own


def test_speaking_during_a_search_keeps_the_head_still():
    """"Let me look." plays while the search turns the head: the body never goes back to swaying mid-search."""
    b, _ = body()
    b.motion.set_mode("searching")
    b.play([0.0] * 160)
    assert b.motion.mode == "searching"
    b.motion.set_mode("idle")
    b.play([0.0] * 160)
    assert b.motion.mode == "idle"


class FocusCamera:
    """v4l2-ctl and a camera whose frames are sharpest at one focus (a checkerboard blurred by the distance from it)."""

    def __init__(self, best=520, flat=False, devices=True):
        self.best, self.flat, self.devices, self.focus, self.auto, self.calls, self._jpegs = best, flat, devices, 0, 1, [], {}

    def run(self, cmd, **kw):
        self.calls.append(cmd)
        if not self.devices:
            raise FileNotFoundError("v4l2-ctl")
        if "--list-devices" in cmd:
            return SimpleNamespace(stdout="Reachy Mini Camera: Reachy Mini (usb-0000:00:14.0-5.2.4):\n\t/dev/video0\n"
                                          "\t/dev/video1\n\t/dev/media0\n")
        for a in cmd:
            k, _, v = a.partition("=")
            if k == "focus_absolute":
                self.focus = int(v)
            elif k == "focus_automatic_continuous":
                self.auto = int(v)
        return SimpleNamespace(stdout="")

    def frame(self):
        import io

        from PIL import Image, ImageFilter

        radius = 0.0 if self.flat else round(min(12.0, abs(self.focus - self.best) / 25.0), 1)
        if radius not in self._jpegs:
            img = Image.new("L", (160, 120))
            img.putdata([255 * ((x // 6 + y // 6) % 2) for y in range(120) for x in range(160)])
            b = io.BytesIO()
            img.filter(ImageFilter.GaussianBlur(radius)).convert("RGB").save(b, "JPEG", quality=90)
            self._jpegs[radius] = b.getvalue()
        return self._jpegs[radius]


def focus_body(cam):
    robot = FakeReachy()
    robot.media = SimpleNamespace(get_frame_jpeg=cam.frame)
    return body(robot, focus=True, run=cam.run)


def test_the_camera_focuses_once_on_the_table_and_holds_it():
    """Measured on the Lite, November 1: autofocus hunted after turns of the head (a view out of focus for 2.5 s),
    and a bunch of keys was found only near one focus. The adapter looks at the table, tries each focus, and holds the
    sharpest, autofocus off; then the head goes back."""
    cam = FocusCamera(best=520)
    b, robot = focus_body(cam)
    assert b.focus_at is not None and abs(b.focus_at - 520) <= 25
    assert cam.auto == 0 and cam.focus == b.focus_at
    assert robot.moves[0][0] == ("pose", 0.0, 15.0)  # it looked at the table to focus
    assert (b.yaw, b.pitch) == (0.0, 0.0)  # and back


def test_without_v4l2_ctl_the_camera_is_left_as_it_was():
    cam = FocusCamera(devices=False)
    b, robot = focus_body(cam)
    assert b.focus_at is None and robot.moves == [] and cam.auto == 1


def test_a_view_with_nothing_to_focus_on_gives_focusing_back_to_the_camera():
    cam = FocusCamera(flat=True)
    b, _ = focus_body(cam)
    assert b.focus_at is None and cam.auto == 1


def test_a_robot_made_up_for_a_test_never_touches_a_camera():
    cam = FocusCamera()
    robot = FakeReachy()
    ReachyBody(robot, pose=lambda yaw, pitch, roll=0.0: ("pose", yaw, pitch), sleep=lambda s: None, run=cam.run)
    assert cam.calls == []


class DippingReachy(ExactReachy):
    """Like the Lite measured on November 1: a look lands where it's sent, but after the pointing dip the head stays
    about 4 degrees low until it's moved again."""

    def goto_target(self, head=None, body_yaw=None, duration=0.5, **kw):
        super().goto_target(head, body_yaw, duration, **kw)
        dipped = len(self.moves) >= 3 and self.moves[-2][0][2] > self.moves[-1][0][2]  # just came back up
        self.sag = 4.0 if dipped else 0.0

    def get_current_head_pose(self):
        _, yaw, pitch = self.moves[-1][0]
        y, p = math.radians(yaw), math.radians(pitch + getattr(self, "sag", 0.0))
        return [[math.cos(y) * math.cos(p), -math.sin(y), 0, 0], [math.sin(y) * math.cos(p), math.cos(y), 0, 0],
                [-math.sin(p), 0, math.cos(p), 0], [0, 0, 0, 1]]


def test_after_the_dip_the_point_is_read_back_and_lifted_once():
    b, robot = body(DippingReachy())
    b.point(20.0, 10.0)
    heads = [m[0] for m in robot.moves]
    assert heads[:3] == [("pose", 20.0, 10.0), ("pose", 20.0, 16.0), ("pose", 20.0, 10.0)]  # face, dip, back
    assert len(heads) == 4 and heads[3][2] == pytest.approx(6.0)  # 4 degrees low: sent 4 higher, once
    assert abs(b.pitch - 10.0) < 1.5


def test_a_point_that_lands_needs_no_correction():
    b, robot = body(ExactReachy())
    b.point(20.0, 10.0)
    assert len(robot.moves) == 3


def test_hearing_goes_on_when_the_microphones_direction_cant_be_read():
    """November 2, 08:08: the microphone array's USB control stopped answering (EIO on every read) and the read of the
    voice's direction raised inside listen(): Andy's hearing thread ended, deaf until restarted. Now the sound still
    comes through, with no direction (the endpointer hears by loudness), and the failures are counted."""
    import threading

    import numpy as np

    b, robot = body()
    stop, chunks = threading.Event(), iter([np.full((160, 2), 0.2, dtype=np.float32)] * 25)

    def doa():
        raise OSError(5, "Input/Output Error")  # what pyusb's USBError is

    robot.media.start_recording = robot.media.stop_recording = lambda: None
    robot.media.get_audio_sample, robot.media.get_DoA = (lambda: next(chunks, None)), doa
    heard = []
    for mono, flag, yaw in b.listen(stop):
        heard.append((len(mono), flag, yaw))
        if len(heard) == 2:
            stop.set()
    assert heard == [(1600, False, None)] * 2 and b.doa_failures == 2
