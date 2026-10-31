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
