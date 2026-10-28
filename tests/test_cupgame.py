from functools import partial

import pytest

from heyandy_meta.companion import cupgame
from heyandy_meta.companion.intents import parse
from heyandy_meta.finder.geometry import pixel_to_angles
from heyandy_meta.models.common import Mask
from heyandy_meta.models.sam_local import Track
from heyandy_meta.robot.body import Frame
from heyandy_meta.robot.sim import Room, SimBody
from heyandy_meta.voice.loop import VoiceLoop
from tests.test_app import andy

SLOTS = (600.0, 960.0, 1320.0)
Y = 700.0
HIDDEN_AT, SHUFFLE = 12, (20, 40)  # the ball vanishes at frame 12; cups 0 and 2 swap over frames 20-40


def cups_at(n: int) -> list[tuple[float, float]]:
    """Cup 0 (with the ball) and cup 2 swap places during the shuffle; cup 1 stays."""
    t = min(1.0, max(0.0, (n - SHUFFLE[0]) / (SHUFFLE[1] - SHUFFLE[0])))
    a, b, c = SLOTS
    return [(a + (c - a) * t, Y), (b, Y), (c + (a - c) * t, Y)]


class Camera:
    """Numbered frames: the scene is decided by the number."""

    def __init__(self, yaw=0.0, pitch=25.0):
        self.n, self.yaw, self.pitch = -1, yaw, pitch

    def grab(self) -> Frame:
        self.n += 1
        return Frame(str(self.n).encode(), 1920, 1080, self.yaw, self.pitch)

    capture = grab


def mask(label, x, y, score=0.9):
    return Mask(label, (int(x - 60), int(y - 90), int(x + 60), int(y + 90)), score, (x, y))


class Sam:
    """Answers like SAM 3.1 would for the numbered frames; ``track`` follows the cups like Object Multiplex."""

    def __init__(self, ball=True, revealed=None):
        self.ball, self.revealed, self.clip = ball, revealed, None

    def find_many(self, frame, things):
        n = int(frame.image)
        out = {"cup": [mask("cup", x, y) for x, y in cups_at(n)], "ball": [], "hand": []}
        if self.ball and n < HIDDEN_AT:
            out["ball"] = [mask("ball", SLOTS[0], Y + 60)]
        if SHUFFLE[0] <= n <= SHUFFLE[1]:
            out["hand"] = [mask("hand", 960, 500)]
        return {t: out[t] for t in things}

    def find(self, frame, thing):
        if thing == "ball" and self.revealed:  # after "lift it up": the ball, in the middle of the view
            return [mask("ball", 960, 542)]
        return self.find_many(frame, [thing])[thing]

    def track(self, frames, query):
        self.clip = [int(f.image) for f in frames]
        tracks = []
        for cup in range(3):
            path = [(k, *cups_at(n)[cup]) for k, n in enumerate(self.clip)]
            tracks.append(Track(10 + cup, path, mask("cup", *path[-1][1:])))
        return tracks


def test_the_cup_with_the_ball_is_followed_through_the_swap():
    cam, sam = Camera(), Sam()
    stages = []
    r = cupgame.play(cam, sam, sam.track, lambda: False, lambda what, **_: stages.append(what), fps=50)
    assert r.how == "found" and r.chosen.id == 10  # cup 0, which ended up where cup 2 started
    assert (r.yaw, r.pitch) == pytest.approx(pixel_to_angles(SLOTS[2], Y, 0.0, 25.0))
    assert stages == ["ball", "seen", "shuffling", "replaying"]
    assert sam.clip[0] <= HIDDEN_AT - 1 and sam.clip[-1] > SHUFFLE[1]  # from the ball's last sighting to the end


def test_no_ball_no_game():
    cam, sam = Camera(), Sam(ball=False)
    assert cupgame.play(cam, sam, sam.track, lambda: False, ball_wait_s=0.3, fps=50).how == "no_ball"


def test_saying_done_ends_the_shuffle_and_replays_it():
    cam, sam = Camera(), Sam()
    r = cupgame.play(cam, sam, sam.track, lambda: cam.n >= 30, fps=50)
    assert r.how == "found" and sam.clip[-1] < 40


def test_the_ball_is_under_the_cup_nearest_where_it_vanished():
    near = Track(1, [(0, 100.0, 100.0), (5, 110.0, 100.0)], None)
    far = Track(2, [(0, 400.0, 100.0), (5, 400.0, 100.0)], None)
    assert cupgame.under([near, far], (112.0, 104.0), 5, within=50) is near
    assert cupgame.under([near, far], (250.0, 100.0), 5, within=50) is None  # nothing close: not a guess


def test_a_cup_dropped_mid_swap_and_found_again_is_one_cup():
    end = Mask("cup", (0, 0, 1, 1), 0.9, (960.0, 640.0))
    dropped = Track(1, [(f, 600.0 + 9 * f, 640.0) for f in range(0, 30)], None)  # heading right, lost at frame 29
    again = Track(7, [(f, 600.0 + 9 * f, 640.0) for f in range(31, 41)], end)  # found again where it was heading
    other = Track(8, [(f, 1300.0, 640.0) for f in range(31, 41)], Mask("cup", (0, 0, 1, 1), 0.9, (1300.0, 640.0)))
    joined = cupgame.stitch([dropped, again, other], near=150)
    assert len(joined) == 2 and joined[0].end is end and joined[0].path[0][0] == 0 and joined[0].path[-1][0] == 40


def test_still_cups_are_not_moving_but_a_different_count_is():
    assert not cupgame.moved([(0, 0), (100, 0)], [(101, 2), (1, 1)], px=5)
    assert cupgame.moved([(0, 0), (100, 0)], [(0, 0), (130, 0)], px=5)
    assert cupgame.moved([(0, 0), (100, 0)], [(0, 0)], px=5)


@pytest.mark.parametrize("text", ["Let's play the cup game", "can we play with the cups", "keep your eye on the ball",
                                  "which cup is the ball under?", "let's play the shell game"])
def test_asking_to_play(text):
    assert parse(text).kind == "game"


def test_keeping_an_eye_on_keys_is_still_watching():
    assert parse("keep an eye on my keys").kind == "watch"


class GameBody(SimBody):
    def __init__(self):
        super().__init__(Room([]))
        self.camera = Camera()

    def capture(self):
        self.log.append(("capture",))
        f = self.camera.grab()
        return Frame(f.image, f.width, f.height, self.yaw, self.pitch)


def test_andy_plays_points_and_keeps_score(tmp_path, monkeypatch):
    monkeypatch.setattr(cupgame, "play", partial(cupgame.play, fps=50))
    a, _, _ = andy(tmp_path=tmp_path)
    body = GameBody()
    sam = Sam(revealed=True)
    a.body, a.segmenter = body, sam
    reply = a.hear("let's play the cup game")
    points = [e for e in body.log if e[0] == "point"]
    assert points and points[-1][1] == pytest.approx(pixel_to_angles(SLOTS[2], Y, 0.0, 25.0)[0], abs=0.01)
    assert "I kept my eye on it" in reply and "1 to 0" in reply
    assert a.screen.snapshot()["models"][0]["name"] == "SAM 3.1 Object Multiplex"
    monkeypatch.setattr(a, "cup_game", lambda: "Another round.")
    assert "Another round." in a.hear("yes please")  # "Again?" answered


def test_without_local_tracking_andy_says_so(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    assert "can't play the cup game" in a.hear("let's play the cup game")


def test_done_reaches_the_game_without_waiting_for_it(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.following = a.playing = True
    assert VoiceLoop(a).heard("okay, done") == "Stopped."
    assert a._stop_following.is_set()
