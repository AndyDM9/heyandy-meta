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


def test_a_find_says_how_far_and_memory_keeps_it(tmp_path):
    a, _, _ = andy(Thing("keys", 15.0, 28.0), tmp_path=tmp_path)
    a.depth = Depth(1.5)
    a.hear("keep an eye on my keys")
    reply = a.hear("where are my keys")
    assert reply.endswith("I see your keys, a little to my left, about 5 feet away.")
    assert a.depth.asked == [(1, 1116)]  # the confirmed thing, with the camera's own focal length
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
