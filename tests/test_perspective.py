import pytest

from heyandy_meta.finder.perspective import from_them, on_plan, words


def test_andys_right_is_the_left_of_someone_facing_andy():
    """The mirror problem: the person two metres in front of Andy; a thing a metre to Andy's right."""
    t = from_them((0.0, 0.0, 2.0), (-90.0, 0.0, 1.0))
    assert t["words"].startswith("ahead of you, on your left") and t["clock"] == 11
    assert t["metres"] == pytest.approx(2.24, abs=0.01)


@pytest.mark.parametrize("thing, said, clock", [
    ((0.0, 0.0, 0.5), "in front of you", 12),        # between them and Andy
    ((0.0, 0.0, 4.0), "behind you", 6),              # beyond them, on the same line
    ((90.0, 0.0, 2.0), "ahead of you, on your right", 2),  # Andy's left is their right: a diagonal, 45 degrees
    ((-60.0, 0.0, 3.0), "on your left", 9),  # 1.5 m ahead of Andy, they're at 2: just in front of them, on their left
    ((-150.0, 0.0, 2.0), "in front of you", 12),  # behind Andy is in front of them, past the robot
])
def test_where_things_are_from_their_side(thing, said, clock):
    t = from_them((0.0, 0.0, 2.0), thing)
    assert t["words"].startswith(said) and t["clock"] == clock


def test_steps_and_beside_you_and_too_close_to_tell():
    assert words(0.0, 0.4) == "right beside you"
    assert words(170.0, 2.8) == "behind you, about 4 steps from you"
    assert words(20.0, 0.7) == "in front of you, about 1 step from you"
    assert from_them((0.0, 0.0, 0.2), (30.0, 0.0, 1.0)) is None  # right up against Andy: which way do they face?


def test_the_plan_is_seen_from_above_with_andy_at_the_middle():
    x, y = on_plan(-90.0, 0.0, 1.0)
    assert (round(x, 3), round(y, 3)) == (1.0, 0.0)  # Andy's right is +x
    x, y = on_plan(0.0, 60.0, 2.0)
    assert (round(x, 3), round(y, 3)) == (0.0, 1.0)  # looking down: the floor distance is shorter


def test_a_find_is_told_from_the_persons_side_when_andy_could_measure_them(tmp_path):
    from heyandy_meta.robot.sim import Thing
    from tests.test_app import andy

    class Depth:  # MapAnything, played: the person 2 m away, the keys 1 m
        def distances(self, frame, masks, cam):
            return [2.0 if masks[0].label == "person" else 1.0]

    a, body, _ = andy(Thing("keys", -90.0, 0.0), Thing("person", 0.0, 0.0, size_px=300), tmp_path=tmp_path)
    a.depth, a.person = Depth(), (0.0, 0.0)
    said = a.hear("where are my keys")
    assert "on your left" in said and "o'clock" in said and "my right" not in said  # Andy's right is their left
    a.person = None  # nobody seen: Andy's own directions, as before
    assert "my right" in a.hear("where are my keys")
