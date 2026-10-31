from heyandy_meta.models.depth_local import how_far
from heyandy_meta.models.sam_local import LocalUnavailable
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy


class Depth:
    """MapAnything's stand-in: every thing is this far away."""

    def __init__(self, metres=1.5, down=False):
        self.metres, self.down, self.asked = metres, down, []

    def distances(self, frame, masks, cam):
        if self.down:
            raise LocalUnavailable("not running")
        self.asked.append((len(masks), round(cam.fx)))
        return [self.metres for _ in masks]


def test_how_far_is_said_roughly_in_feet():
    assert how_far(1.5) == "about 5 feet away"
    assert how_far(0.25) == "about a foot away"
    assert how_far(3.0) == "about 10 feet away"


def test_in_spanish_how_far_is_said_in_metres():
    assert how_far(0.62, metric=True) == "about 60 centimetres away"
    assert how_far(0.04, metric=True) == "about 10 centimetres away"
    assert how_far(1.04, metric=True) == "roughly one metre away"
    assert how_far(1.3, metric=True) == "about 1.5 metres away"
    assert how_far(2.1, metric=True) == "about 2 metres away"


def test_a_find_says_how_far_and_memory_keeps_it(tmp_path):
    a, _, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.depth = Depth(1.5)
    a.hear("keep an eye on my keys")
    reply = a.hear("where are my keys")
    assert reply.endswith("I see your keys, a little to my left, about 5 feet away.")
    assert a.depth.asked == [(1, 1054)]  # the confirmed thing, with the camera's own focal length
    assert a.places.history("keys")[-1]["metres"] == 1.5
    assert any(s.startswith("MapAnything: 1.5 m") for s in a.screen.snapshot()["steps"])


def test_without_mapanything_andy_says_the_direction_only(tmp_path):
    a, _, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.depth = Depth(down=True)
    assert a.hear("where are my keys").endswith("I see your keys, a little to my left.")


def test_the_memory_list_and_the_map_carry_the_distance(tmp_path):
    a, _, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.depth = Depth(1.5)
    a.hear("keep an eye on my keys")
    a.hear("where are my keys")
    snap = a.screen.snapshot()
    assert snap["map"][0]["metres"] == 1.5
    assert any("about 5 feet away" in line for line in snap["watching"])


class Scanner:
    """MapAnything's /scan, played: the things it was shown, placed where they are, and a little shape."""

    def __init__(self):
        self.looks = []

    def scan(self, looks):
        import struct

        self.looks.append([(f.yaw, [m.label for m in masks]) for f, _, masks in looks])
        seen = [{"label": m.label, "score": 0.9, "point": [0.3, 0.2, 0.6], "metres": 0.7} for _, _, ms in looks for m in ms]
        return {"points": struct.pack("<6e", 0.1, 0.9, 1.0, -0.2, 0.3, 0.8), "n": 2, "things": seen, "seconds": 1.4}


def test_show_me_the_room_measures_it_in_3d_and_remembers_watched_things(tmp_path):
    from heyandy_meta.app import millimetres, room_things
    from heyandy_meta.companion.intents import parse

    assert parse("Andy, show me the room").kind == "room" and parse("scan the room in 3D").kind == "room"
    assert parse("draw me a map of my things").kind != "room" and parse("show me the weather radar on the TV").kind == "web"
    a, body, _ = andy(Thing("keys", -26.0, 20.0), tmp_path=tmp_path)
    a.places.watch("keys")
    a.depth = Scanner()
    said = a.hear("Andy, show me the room")
    assert "measured it" in said and "your keys" in said and "never a picture" in said
    assert len(a.depth.looks[0]) == 5  # five looks across the room
    snap = a.screen.snapshot()
    assert snap["room"]["n"] == 2 and snap["room"]["things"][0]["label"] == "keys"
    assert a.screen.room_bytes() == millimetres(__import__("struct").pack("<6e", 0.1, 0.9, 1.0, -0.2, 0.3, 0.8))
    assert a.places.metres("keys") == 0.7  # the scan updates where a watched thing is
    assert room_things([{"label": "keys", "score": 0.6, "point": [0.5, 0.2, 0.3]}]) == []  # once, and unsure: dropped
