import math

import pytest

from heyandy_meta.robot.motion import UPRIGHT, Motion, Pose


def run(m, t0, t1, base=Pose(), step=0.02):
    poses, t = [], t0
    while t <= t1:
        poses.append(m.pose(t, base))
        t += step
    return poses


def test_idle_breathes_gently_around_the_base():
    m = Motion()
    poses = run(m, 0, 10, Pose(yaw=20.0, pitch=10.0))
    pitches = [p.pitch for p in poses]
    assert max(pitches) - min(pitches) == pytest.approx(2 * m.breathe_pitch, abs=0.1)
    assert all(p.yaw == 20.0 for p in poses)


def test_searching_holds_the_head_still():
    m = Motion()
    m.set_mode("searching")
    poses = run(m, 0, 3, Pose(yaw=-30.0, pitch=15.0))
    still = poses[30:]  # after the fade
    assert all(p.pitch == pytest.approx(15.0) and p.antennas == pytest.approx(UPRIGHT) for p in still)


def test_modes_fade_in_without_jumps():
    m = Motion()
    run(m, 0, 2)
    m.set_mode("listening")
    poses = run(m, 2.02, 3)
    jumps = [abs(a.antennas[1] - b.antennas[1]) for a, b in zip(poses, poses[1:])]
    assert max(jumps) < 0.05  # under 2.5 rad/s at 50 Hz
    assert poses[-1].antennas[1] > UPRIGHT[1] + 0.15  # spread once faded in


def test_speaking_moves_with_the_words():
    m = Motion()
    m.set_mode("speaking")
    m.speech = (0.0, 0.0, 0.003, math.radians(2), math.radians(3), math.radians(-4))
    p = run(m, 0, 1)[-1]
    assert p.yaw == pytest.approx(-4.0, abs=0.01) and p.roll == pytest.approx(2.0, abs=0.01)


def test_antennas_stay_inside_their_range():
    m = Motion()
    m.set_mode("thinking")
    m.speech = (0, 0, 0, 0, 1.0, 0)
    m.wiggle(0, 10)
    for p in run(m, 0, 10):
        assert -1.2 <= p.antennas[0] <= 0.6 and -0.6 <= p.antennas[1] <= 1.2


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        Motion().set_mode("dance")
