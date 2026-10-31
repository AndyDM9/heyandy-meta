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
                yaw, _ = turn(lambda: read(head[0]), lambda y: head.__setitem__(0, y), start)
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
