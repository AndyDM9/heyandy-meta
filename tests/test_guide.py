import math

import pytest

from heyandy_meta.companion.guide import (ES, THERE_M, covered, guide, height_above, instruction, note, on_surface,
                                          their_way)
from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.language import PHRASES
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.body import Frame
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy, said

IN_FRONT = (0.0, 1.0)  # the person, on the plan: a metre in front of Andy, facing it


@pytest.mark.parametrize("hand, thing, words", [
    ((0.2, 0.5), (0.0, 0.5), "Right."),  # the hand to Andy's right is to the person's left: the thing is to their right
    ((-0.2, 0.5), (0.0, 0.5), "Left."),
    ((0.0, 0.8), (0.0, 0.5), "Further."),  # the hand nearer them than the thing: reach further
    ((0.0, 0.2), (0.0, 0.5), "Toward you."),
    ((0.25, 0.75), (0.0, 0.5), "Further, and right."),
    ((0.05, 0.5), (-0.05, 0.5), "A little right."),
    ((0.0, 0.55), (0.0, 0.5), ""),  # within reach: it's there
])
def test_the_way_is_said_from_the_persons_side(hand, thing, words):
    assert instruction(*their_way(IN_FRONT, hand, thing)) == words


def test_someone_beside_andy_gets_their_own_left_and_right():
    beside = (-1.0, 0.0)  # at Andy's left, facing it: their "further" is Andy's right
    right, further = their_way(beside, (-0.3, 0.3), (0.0, 0.3))
    assert further == pytest.approx(0.3) and abs(right) < 1e-9


def test_a_hand_over_the_table_is_placed_by_the_tables_height():
    h = height_above(25.0, 0.6)  # a thing 0.6 m away, 25 degrees down: the camera is about 0.25 m above its surface
    assert h == pytest.approx(0.6 * math.sin(math.radians(25)))
    x, y = on_surface(0.0, 25.0, h)
    assert x == pytest.approx(0.0, abs=1e-9) and math.hypot(x, y) == pytest.approx(0.6 * math.cos(math.radians(25)))
    assert height_above(25.0, None) == 0.22 and height_above(1.0, 2.0) == 0.22  # unmeasured, or level with the eyes


def test_the_notes_rise_as_the_hand_nears_and_a_covered_thing_counts():
    assert [note(m) for m in (0.8, 0.45, 0.3, 0.15, 0.02)] == ["near1", "near1", "near3", "near4", "near5"]
    assert covered((0, 0, 100, 100), (50, 50, 150, 150)) == pytest.approx(0.25)
    assert covered((0, 0, 10, 10), (50, 50, 60, 60)) == 0


def test_every_guiding_word_has_spanish_without_a_translator():
    for right, further in ((-0.3, 0.0), (0.3, 0.0), (0.0, 0.3), (0.0, -0.3), (0.2, 0.2), (-0.2, -0.2), (0.06, 0.06)):
        words = instruction(right, further)
        assert ES[words] and PHRASES["es"][words] == ES[words]
    assert ES["Further, and left."] == "Más lejos, y a la izquierda." and ES["A little toward you."] == "Un poco hacia usted."


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def wait(self, s):
        self.t += s


class Body:
    def __init__(self):
        self.frames = 0

    def capture(self):
        self.frames += 1
        return Frame(b"", 1920, 1080, 0.0, 20.0)


class Hands:
    """SAM 3.1, scripted: the mug in the middle of the view, and a hand that comes in from Andy's right."""

    def __init__(self, path, mug=True):
        self.path, self.mug, self.n = list(path), mug, 0

    def find_many(self, frame, queries):
        at = self.path[min(self.n, len(self.path) - 1)]
        self.n += 1
        mug = [Mask("mug", (930, 520, 990, 580), 0.9, (960.0, 550.0), 3600)] if self.mug else []
        hand = [] if at is None else [Mask("hand", (int(at[0]) - 60, int(at[1]) - 40, int(at[0]) + 60, int(at[1]) + 40), 0.8,
                                           at, 9600)]
        return {"mug": mug, "hand": hand}


def run(segmenter, stop=lambda: False, seconds=40.0):
    clock, log = Clock(), []
    r = guide(Body(), segmenter, "mug", (0.0, 20.0), 0.22, IN_FRONT, lambda w: log.append(("say", w)),
              lambda n: log.append(("note", n)), lambda *a: log.append(("frame", a[4], a[5])), stop, seconds,
              clock=clock, wait=clock.wait)
    return r, log, clock


def test_the_hand_is_talked_in_and_it_ends_when_the_hand_is_there():
    path = [None, (1500, 560), (1400, 560), (1300, 556), (1200, 552), (1100, 550), (1020, 550), (965, 550)]
    r, log, clock = run(Hands(path))
    words = [e[1] for e in log if e[0] == "say"]
    assert words[0] == "Right."  # to Andy's right in the picture is to the person's left: the mug is to their right
    assert any(e[0] == "note" for e in log)  # the same words aren't said every frame: a note instead
    assert r.why == "there" and r.closest is not None and r.closest <= THERE_M
    assert r.frames >= 5 and clock.t >= 0.4 * (r.frames - 1)  # paced: a frame every 0.4 s at most


def test_no_hand_no_words_but_a_reminder_and_it_gives_up_in_time():
    r, log, _ = run(Hands([None]), seconds=20.0)
    assert r.why == "no hand" and [e[1] for e in log if e[0] == "say"] == ["I can't see your hand."] * 2


def test_stop_and_a_lost_thing_end_it():
    assert run(Hands([(1500, 560)]), stop=lambda: True)[0].why == "stopped"
    assert run(Hands([(1500, 560)], mug=False))[0].why == "lost"


def test_a_hand_that_covers_the_thing_once_close_is_there():
    seg = Hands([(1100, 550), (1000, 550)])
    real = seg.find_many

    def covering(frame, queries):
        out = real(frame, queries)
        return {**out, "mug": out["mug"] if seg.n <= 2 else []}  # the hand over the mug: SAM sees only the hand

    seg.find_many = covering
    r, _, _ = run(seg)
    assert r.why == "there"


@pytest.mark.parametrize("said_, thing", [("Hey Andy, help me reach it", ""), ("guide my hand to my keys", "keys"),
                                          ("help me reach my glasses please", "glasses"), ("guíeme", ""),
                                          ("can you help me grab the mug?", "mug")])
def test_guiding_is_asked_for_in_plain_words(said_, thing):
    i = parse(said_)
    assert i.kind == "guide" and i.thing == thing
    assert parse("help me find my keys").kind == "find"


def test_andy_finds_then_talks_the_hand_onto_the_keys(tmp_path):
    hand = Thing("hand", -38.0, 16.0, size_px=120)
    a, body, clock = andy(Thing("keys", -20.0, 25.0), hand, tmp_path=tmp_path)
    a.wait = lambda s: setattr(clock, "t", clock.t + s)
    capture = body.capture

    def reaching():  # the hand moves a third of the way to the keys between frames
        hand.yaw += (-20.0 - hand.yaw) / 3
        hand.pitch += (25.0 - hand.pitch) / 3
        return capture()

    a.hear("where are my keys")
    body.capture = reaching
    body.log.clear()
    words = a.hear("help me reach them")
    assert words == "That's it! Your keys are right at your fingertips."
    spoken = said(body)
    assert spoken[0] == "Put your hand out toward it, and I'll guide you."
    assert any("right" in w.lower() for w in spoken[1:])  # the keys are to the left of the hand in Andy's view
    assert ("chime", "found") in body.log and not a.following


def test_nothing_found_yet_asks_which_thing(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "Which thing" in a.hear("guide my hand")


def test_the_tv_shows_the_hand_the_thing_and_the_way():
    s = ScreenState()
    frame = Frame(b"\xff\xd8jpeg", 1920, 1080, 0.0, 20.0)
    mug, hand = Mask("mug", (930, 520, 990, 580), 0.9, (960.0, 550.0)), Mask("hand", (1100, 500, 1300, 600), 0.8, (1200.0, 550.0))
    s.guiding("mug", frame, mug, hand, "Further, and right.", 45, 0.31)
    g = s.snapshot()["guide"]
    assert g["words"] == "Further, and right" and g["way"] == 45 and g["cm"] == 31 and g["hand"]["center"] == [1200, 550]
    assert g["src"].startswith("data:image/jpeg;base64,") and not g["done"]
    s.guided("That's it!")
    assert s.snapshot()["guide"]["done"] and s.snapshot()["guide"]["words"] == "That's it!"
    s.clear()
    assert s.snapshot()["guide"] is None
