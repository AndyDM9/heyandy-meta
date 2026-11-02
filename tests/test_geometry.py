import math

import pytest

from heyandy_meta.finder.geometry import LITE, Sighting, angles_to_pixel, merge, pixel_to_angles


def test_centre_pixel_is_the_view_itself():
    assert pixel_to_angles(LITE.cx, LITE.cy, 18.0, 15.0) == pytest.approx((18.0, 15.0))


def test_left_is_positive_yaw_and_down_is_positive_pitch():
    assert pixel_to_angles(LITE.cx - LITE.fx, LITE.cy, 0.0, 0.0) == pytest.approx((45.0, 0.0))
    assert pixel_to_angles(LITE.cx, LITE.cy + LITE.fx, 0.0, 0.0) == pytest.approx((0.0, 45.0))


def test_a_corner_is_the_pixels_ray_not_two_angles_added():
    """A pixel a focal length left and a focal length down: its ray is 45 degrees left but only 35.3 down (the
    old sum said 45 and 45)."""
    yaw, pitch = pixel_to_angles(LITE.cx - LITE.fx, LITE.cy + LITE.fx, 0.0, 0.0)
    assert yaw == pytest.approx(45.0) and pitch == pytest.approx(35.26, abs=0.01)


def test_with_the_head_tilted_down_the_side_of_the_frame_is_higher():
    """Measured on our Lite, November 1: the same things seen from 36 directions disagreed by up to 7.8 degrees with
    the angles added, about 3 with the ray turned. The middle row, 38 degrees to the side, in a view 15 degrees down:
    about 11.8 degrees down, not 15."""
    x = LITE.cx - LITE.fx * math.tan(math.radians(38.0))
    yaw, pitch = pixel_to_angles(x, LITE.cy, 0.0, 15.0)
    assert pitch == pytest.approx(math.degrees(math.asin(math.sin(math.radians(15)) * math.cos(math.radians(38)))), abs=0.05)
    assert 11.5 < pitch < 12.1 and 38.5 < yaw < 39.5


@pytest.mark.parametrize("view", [(0.0, 0.0), (18.0, 15.0), (-55.0, 25.0), (110.0, -5.0)])
@pytest.mark.parametrize("px", [(953.0, 542.0), (100.0, 80.0), (1800.0, 1000.0), (400.0, 900.0)])
def test_angles_to_pixel_undoes_pixel_to_angles(view, px):
    yaw, pitch = pixel_to_angles(*px, *view)
    assert angles_to_pixel(yaw, pitch, *view) == pytest.approx(px, abs=1e-6)


def test_a_direction_behind_the_camera_is_in_no_pixel():
    assert angles_to_pixel(180.0, 0.0, 0.0, 0.0) is None


def test_frame_edge_is_about_forty_two_degrees():
    yaw, _ = pixel_to_angles(0, LITE.cy, 0.0, 0.0)
    assert 41.5 < yaw < 42.5  # half of the ~84 degrees across measured on our Lite (published: ~81)


def test_scaled_camera_gives_the_same_angle():
    small = LITE.scaled(960, 540)
    assert pixel_to_angles(100, 100, 0, 0, small) == pytest.approx(pixel_to_angles(200, 200, 0, 0), abs=0.05)


def test_overlapping_views_merge_into_one_place():
    places = merge([Sighting(20.0, 10.0, 0.6), Sighting(22.0, 11.0, 0.9), Sighting(-30.0, 10.0, 0.95)])
    assert len(places) == 2
    assert places[0].views == 2
    assert places[0].yaw == pytest.approx(21.0)
    assert places[0].score == pytest.approx(0.9)
