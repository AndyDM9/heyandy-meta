import pytest

from heyandy_meta.finder.geometry import LITE, Sighting, merge, pixel_to_angles


def test_centre_pixel_is_the_view_itself():
    assert pixel_to_angles(LITE.cx, LITE.cy, 18.0, 15.0) == pytest.approx((18.0, 15.0))


def test_left_is_positive_yaw_and_down_is_positive_pitch():
    yaw, pitch = pixel_to_angles(LITE.cx - LITE.fx, LITE.cy + LITE.fx, 0.0, 0.0)
    assert yaw == pytest.approx(45.0)
    assert pitch == pytest.approx(45.0)


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
