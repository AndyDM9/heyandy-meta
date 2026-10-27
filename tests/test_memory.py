import json
import stat

import pytest

from heyandy_meta.finder.search import Finder
from heyandy_meta.memory.glance import glance
from heyandy_meta.memory.places import Places
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing


def test_only_watched_things_are_remembered(tmp_path):
    places = Places(tmp_path / "p.json")
    assert not places.saw("keys", 10, 10)
    places.watch("keys")
    assert places.saw("keys", 10.04, 9.96)
    assert places.last_seen("keys") == (10.0, 10.0)


def test_forget_removes_the_wish_and_the_place(tmp_path):
    places = Places(tmp_path / "p.json")
    places.watch("keys")
    places.saw("keys", 10, 10)
    places.forget("keys")
    assert places.watching() == [] and places.last_seen("keys") is None
    assert "keys" not in (tmp_path / "p.json").read_text()


def test_old_sightings_are_not_trusted(tmp_path):
    places = Places(tmp_path / "p.json", max_age_s=60)
    places.watch("keys")
    places.saw("keys", 10, 10, when=1000.0)
    assert places.last_seen("keys", now=1030.0) == (10.0, 10.0)
    assert places.last_seen("keys", now=1100.0) is None


def test_the_file_holds_no_pictures_and_only_its_owner_can_read_it(tmp_path):
    places = Places(tmp_path / "p.json")
    places.watch("glasses")
    places.saw("glasses", 5, 5)
    f = tmp_path / "p.json"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert set(json.loads(f.read_text())["seen"]["glasses"]) == {"yaw", "pitch", "at"}
    assert Places(f).last_seen("glasses") == (5.0, 5.0)  # survives a restart


def test_a_glance_notes_watched_things_only(tmp_path):
    room = Room([Thing("keys", -30.0, 20.0), Thing("remote", 25.0, 15.0)])
    places = Places(tmp_path / "p.json")
    places.watch("keys")
    noted = glance(SimBody(room), SimSegmenter(room), places)
    assert set(noted) == {"keys"}
    assert places.last_seen("keys") == pytest.approx((-30.0, 20.0), abs=0.5)


def test_the_finder_goes_straight_to_where_the_glance_saw_it(tmp_path):
    room = Room([Thing("keys", -30.0, 20.0)])
    body, seg = SimBody(room), SimSegmenter(room)
    places = Places(tmp_path / "p.json")
    places.watch("keys")
    glance(body, seg, places)
    found = Finder(body, seg).find("keys", last_seen=places.last_seen("keys"))
    assert found.remembered and found.looks == 1


def test_nothing_watched_means_no_looking(tmp_path):
    room = Room([Thing("keys", 0.0, 10.0)])
    body = SimBody(room)
    assert glance(body, SimSegmenter(room), Places(tmp_path / "p.json")) == {}
    assert body.log == []
