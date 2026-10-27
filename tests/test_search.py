import pytest

from heyandy_meta.finder.search import Finder
from heyandy_meta.robot.body import Reach
from heyandy_meta.robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing


def finder(*things, reach=Reach(), **kw):
    room = Room(list(things))
    body = SimBody(room, reach)
    return Finder(body, SimSegmenter(room), **kw), body, room


def pointed(body):
    return [e for e in body.log if e[0] == "point"]


def test_finds_and_points_within_a_degree():
    f, body, _ = finder(Thing("glasses", 30.0, 20.0))
    found = f.find("glasses")
    assert found.yaw == pytest.approx(30.0, abs=0.5) and found.pitch == pytest.approx(20.0, abs=0.5)
    assert pointed(body) == [("point", round(found.yaw, 2), round(found.pitch, 2))]
    assert found.looks == 2  # confident in the first view, so it looks closer at once


def test_absent_means_no_point_and_no_guess():
    f, body, _ = finder(Thing("keys", 30.0, 20.0))
    assert f.find("glasses") is None
    assert pointed(body) == []


def test_seen_from_two_views_is_one_place():
    f, _, _ = finder(Thing("remote", 36.0, 10.0, score=0.6))  # inside both the 55 and the 18 degree views
    assert f.find("remote").looks == 5  # not sure enough to stop early: four views, then one closer look


def test_a_sure_sighting_stops_the_sweep_but_a_wrong_one_does_not():
    f, body, room = finder(Thing("keys", 50.0, 10.0, on_screen=True), Thing("keys", -50.0, 15.0))
    f.check = SimJudge(room).real
    found = f.find("keys")
    assert found.yaw == pytest.approx(-50.0, abs=0.5)  # the TV picture got its closer look and was turned down


def test_past_the_head_reach_the_base_turns():
    f, body, _ = finder(Thing("glasses", 74.0, 20.0))  # where all six October 20 misses were
    found = f.find("glasses")
    assert found.yaw == pytest.approx(74.0, abs=0.5) and found.reachable
    assert pointed(body)[0][1] == pytest.approx(74.0, abs=0.5)


def test_beyond_any_reach_it_says_so_instead_of_pretending():
    f, body, _ = finder(Thing("glasses", 74.0, 20.0), reach=Reach(yaw=60.0))  # head only
    found = f.find("glasses")
    assert found.yaw == pytest.approx(74.0, abs=0.5)
    assert not found.reachable
    assert pointed(body)[0][1] == 60.0  # clamped by the body, not by the finder


def test_a_picture_on_the_tv_is_rejected_by_the_check():
    tv = Thing("glasses", -40.0, 5.0, score=0.95, on_screen=True)
    real = Thing("glasses", 20.0, 22.0, score=0.8)
    room_things = [tv, real]

    def not_on_a_screen(frame, mask):
        return not any(t.on_screen and abs(t.yaw - frame.yaw) < 3 for t in room_things)

    f, _, _ = finder(*room_things, check=not_on_a_screen)
    found = f.find("glasses")
    assert found.yaw == pytest.approx(20.0, abs=0.5)


def test_remembered_place_is_checked_first():
    f, _, _ = finder(Thing("keys", -25.0, 18.0))
    found = f.find("keys", last_seen=(-25.0, 18.0))
    assert found.remembered and found.looks == 1


def test_moved_since_last_seen_falls_back_to_the_sweep():
    f, _, _ = finder(Thing("keys", 40.0, 18.0))
    found = f.find("keys", last_seen=(-25.0, 18.0))
    assert not found.remembered and found.yaw == pytest.approx(40.0, abs=0.5)


def test_weak_detections_are_ignored():
    f, _, _ = finder(Thing("glasses", 30.0, 20.0, score=0.1))
    assert f.find("glasses") is None
