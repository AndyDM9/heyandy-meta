import sys
from pathlib import Path

import pytest

pytest.importorskip("reachy_mini")  # the app needs Pollen's SDK (the robot extra); CI runs without it
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "andy_finder"))
from andy_finder.main import side, where_to_look  # noqa: E402


def test_the_middle_of_the_picture_is_where_the_head_looks():
    assert where_to_look(953, 542, 1920, 1080, 20.0, 10.0) == pytest.approx((20.0, 10.0))


def test_left_in_the_picture_is_left_for_the_robot_at_any_size():
    yaw, _ = where_to_look(100, 270, 960, 540, 0.0, 15.0)
    assert yaw > 15 and side(yaw).endswith("left")


def test_side_in_words():
    assert side(3) == "straight ahead" and side(-20) == "a little to my right" and side(60) == "to my left"


def test_the_page_has_every_element_its_script_uses():
    import re

    static = Path(__file__).resolve().parents[1] / "apps" / "andy_finder" / "andy_finder" / "static"
    page, script = (static / "index.html").read_text(), (static / "main.js").read_text()
    used = set(re.findall(r'\$\("([\w-]+)"\)', script))
    assert used and used <= set(re.findall(r'id="([\w-]+)"', page))
    assert (static / "fonts" / "AtkinsonHyperlegibleNext.ttf").exists() and (static / "fonts" / "OFL.txt").exists()


def test_ring_it_places_the_ringing_as_andy_does_from_any_start():
    """Andy Finder's copy of companion/sound.py: the same answer, so the app store's app turns as Andy does."""
    from andy_finder.main import turn_to as app_turn

    from heyandy_meta.companion.sound import turn_to as andy_turn

    for source in (-60.0, -15.0, 30.0):
        for start in (-50.0, 0.0, 50.0):
            def read(head, s=source):
                return 0.0 if abs(s - head) < 15 else 0.3 * (s - head)
            ends = []
            for turn in (app_turn, andy_turn):
                head = [start]
                yaw, _ = turn(lambda h=head: read(h[0]), lambda y, h=head: h.__setitem__(0, y), start)
                ends.append(yaw)
            assert ends[0] == ends[1] and abs(ends[0] - source) <= 15


def test_ring_it_hears_a_ringtone_and_not_a_voice():
    import numpy as np

    from andy_finder.main import flatness, reading

    t = np.arange(1600) / 16000
    assert flatness(0.3 * (np.sin(2 * np.pi * 1400 * t) + np.sin(2 * np.pi * 1750 * t))) < 0.015
    rings = [(i, 0.2, 0.002, -20.0) for i in range(6)]
    assert reading(rings, 0.01) == -20.0
    talk = [(i, 0.2, 0.05, 10.0) for i in range(8)] + [(9, 0.2, 0.004, 10.0)] * 3  # tonal only now and then
    assert reading(talk, 0.01) is None


def test_the_app_store_app_turns_each_pixel_as_andy_does():
    """Andy Finder's copy of finder/geometry.py's true ray: the same head direction for any pixel and view."""
    from heyandy_meta.finder.geometry import LITE, pixel_to_angles

    for x, y, yaw, pitch in [(100, 100, 0, 15), (1800, 1000, 30, 20), (960, 540, -40, 5), (50, 1050, 55, 25)]:
        assert where_to_look(x, y, 1920, 1080, yaw, pitch) == pytest.approx(pixel_to_angles(x, y, yaw, pitch, LITE))
    assert where_to_look(25, 525, 960, 540, 10, 15) == pytest.approx(pixel_to_angles(50, 1050, 10, 15, LITE), abs=1e-6)


def test_how_far_off_a_point_is():
    from andy_finder.main import off_middle

    assert off_middle(953, 542, 1920, 1080) == pytest.approx(0.0)
    assert off_middle(953 + 1054, 542, 1920, 1080) == pytest.approx(45.0)
    assert off_middle(476.5, 271 + 527 * 0.1, 960, 540) == pytest.approx(5.71, abs=0.01)


def test_the_head_read_back_from_the_daemon_pose():
    from reachy_mini.utils import create_head_pose

    from andy_finder.main import head_angles

    assert head_angles(create_head_pose(yaw=25, pitch=12, degrees=True)) == pytest.approx((25, 12), abs=1e-6)


def _v4l2(listing="Reachy Mini Camera: Reachy Mini (usb-0000:00:14.0-2):\n\t/dev/video0\n\t/dev/video1\n\n", auto=1):
    """A stand-in for v4l2-ctl: records each call, answers the list and the autofocus reading."""
    from types import SimpleNamespace

    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd == ["v4l2-ctl", "--list-devices"]:
            return SimpleNamespace(stdout=listing)
        if "--get-ctrl" in cmd:
            return SimpleNamespace(stdout=f"focus_automatic_continuous: {auto}\n")
        return SimpleNamespace(stdout="")
    return run, calls


def _jpeg(blur: float) -> bytes:
    import io as io_

    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.default_rng(1)
    img = Image.fromarray((rng.random((90, 160)) * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(blur))
    b = io_.BytesIO()
    img.save(b, "JPEG", quality=95)
    return b.getvalue()


def test_the_focus_is_held_where_the_table_is_sharpest_and_given_back_as_it_was():
    from andy_finder.main import Focus

    run, calls = _v4l2(auto=1)
    lens = {"at": 0}

    def fake(cmd, **kw):
        for i, a in enumerate(cmd):
            if a == "-c" and cmd[i + 1].startswith("focus_absolute="):
                lens["at"] = int(cmd[i + 1].split("=")[1])
        return run(cmd, **kw)
    focus = Focus(run=fake)
    assert focus.dev == "/dev/video0"
    looked = []
    held = focus.hold(lambda y, p: looked.append((y, p)), lambda: _jpeg(abs(lens["at"] - 520) / 25), settle_s=0)
    assert held in (500, 537) and looked == [(0.0, 15.0)]
    assert ["v4l2-ctl", "-d", "/dev/video0", "-c", "focus_automatic_continuous=0"] in calls
    assert calls[-1] == ["v4l2-ctl", "-d", "/dev/video0", "-c", f"focus_absolute={held}"]
    focus.release()
    assert calls[-1] == ["v4l2-ctl", "-d", "/dev/video0", "-c", "focus_automatic_continuous=1"]


def test_a_blank_view_leaves_autofocus_on_and_no_camera_changes_nothing():
    from andy_finder.main import Focus

    run, calls = _v4l2()
    assert Focus(run=run).hold(lambda y, p: None, lambda: _jpeg(1.0), settle_s=0) is None
    assert calls[-1][-1] == "focus_automatic_continuous=1"
    run, calls = _v4l2(listing="Integrated Webcam (usb-0000:00:14.0-5):\n\t/dev/video0\n\n")
    focus = Focus(run=run)
    assert focus.dev is None and focus.hold(lambda y, p: None, lambda: b"", settle_s=0) is None
    focus.release()
    assert calls == [["v4l2-ctl", "--list-devices"]]


def test_focus_held_by_something_else_stays_held_after_the_app():
    from andy_finder.main import Focus

    run, calls = _v4l2(auto=0)
    focus = Focus(run=run)
    focus.hold(lambda y, p: None, lambda: _jpeg(1.0), settle_s=0)
    focus.release()
    assert calls[-1][-1] == "focus_automatic_continuous=0"


def test_ring_it_keeps_listening_when_the_arrays_usb_read_fails():
    """Pollen's SDK raises on a failed direction read (1.12 and 1.13), though its docstring says None."""
    from types import SimpleNamespace

    from andy_finder.main import side_heard

    def broken():
        raise OSError(5, "Input/Output Error")

    assert side_heard(SimpleNamespace(get_DoA=broken)) is None
    assert side_heard(SimpleNamespace(get_DoA=lambda: (0.0, True))) == pytest.approx(90.0)  # 0 rad is the left
    assert side_heard(SimpleNamespace(get_DoA=lambda: (1.2, False))) is None  # no speech or ringing detected
