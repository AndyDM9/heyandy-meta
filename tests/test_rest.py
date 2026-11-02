"""Andy rests when nobody's there (companion/rest.py): the breath stops, and SAM 3.1 is asked only when the picture
changes. Synthetic pictures only."""
import io
import random
from dataclasses import dataclass, field

import pytest
from PIL import Image, ImageDraw

from heyandy_meta.companion.rest import LEAST, REST_AFTER_S, Rest, check
from heyandy_meta.robot.motion import REST_FADE_S, Motion, Pose


def room(person: bool = False, noise: float = 0.0, light: int = 0, seed: int = 1) -> bytes:
    """A 640x360 room: a wall, a table, a lamp; a person standing by the table if asked; sensor noise if asked."""
    img = Image.new("L", (640, 360), 120 + light)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 250, 640, 360), fill=70 + light)  # the floor
    d.rectangle((380, 180, 560, 260), fill=40 + light)  # the table
    d.ellipse((60, 40, 120, 100), fill=230)  # the lamp
    if person:
        d.rectangle((250, 110, 310, 330), fill=20)
        d.ellipse((255, 60, 305, 110), fill=200)
    if noise:
        rnd = random.Random(seed)
        px = img.load()
        for y in range(0, 360):
            for x in range(0, 640):
                px[x, y] = max(0, min(255, int(px[x, y] + rnd.gauss(0, noise))))
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=80)
    return out.getvalue()


def test_rests_only_after_ten_quiet_minutes_and_not_while_busy():
    r = Rest(woke_at=0.0)
    assert not r.due(REST_AFTER_S - 1, last_turn=float("-inf"), busy=False)  # Andy has only just started
    assert r.due(REST_AFTER_S, last_turn=float("-inf"), busy=False)
    assert not r.due(REST_AFTER_S + 100, last_turn=200.0, busy=False)  # a turn 7 minutes ago
    assert not r.due(REST_AFTER_S * 3, last_turn=0.0, busy=True)
    r.begin(1000.0)
    assert not r.due(5000.0, last_turn=0.0, busy=False)  # already resting
    r.wake(5000.0)
    assert not r.due(5000.0 + REST_AFTER_S - 1, last_turn=0.0, busy=False)  # woke by someone there: ten more minutes
    assert Rest(after_s=float("inf")).due(1e12, float("-inf"), False) is False  # --no-rest


def test_a_still_room_never_asks_sam_and_a_person_coming_in_does():
    r = Rest()
    r.begin(0.0)
    assert r.changed(room(), 0.0, 0.0) is False  # the first picture is the room
    for seed in range(5):  # the camera's own noise, frame to frame
        assert r.changed(room(noise=4.0, seed=seed), 0.0, 0.0) is False
    assert r.still == 5 and r.looks == 0
    assert r.changed(room(person=True), 0.0, 0.0) is True
    assert r.looks == 1


def test_nobody_found_makes_the_new_picture_the_room():
    r = Rest()
    r.begin(0.0)
    r.changed(room(), 0.0, 0.0)
    assert r.changed(room(light=60), 0.0, 0.0) is True  # a lamp went on: a change, so SAM is asked once
    r.nobody(room(light=60), 0.0, 0.0)  # and finds nobody
    assert r.changed(room(light=60), 0.0, 0.0) is False  # so the lit room is the room now


def test_another_way_of_looking_is_a_new_picture_not_a_change():
    r = Rest()
    r.begin(0.0)
    r.changed(room(), 0.0, 0.0)
    assert r.changed(room(person=True), 30.0, 0.0) is False  # a glance round the room: another view
    assert r.changed(room(person=True), 30.0, 0.0) is False
    assert r.looks == 0


def test_a_small_thing_is_enough_but_a_few_pixels_are_not():
    from heyandy_meta.companion.rest import changed_share, grey

    small = Image.open(io.BytesIO(room())).copy()
    ImageDraw.Draw(small).rectangle((300, 200, 330, 230), fill=255)  # a cup put on the floor, 30 pixels a side
    out = io.BytesIO()
    small.save(out, "JPEG", quality=80)
    assert changed_share(grey(room()), grey(out.getvalue())) >= LEAST


# --- check(): the thread's one look ---

@dataclass
class Frame:
    image: bytes
    yaw: float = 0.0
    pitch: float = 0.0


@dataclass
class Mask:
    score: float


@dataclass
class Body:
    motion: Motion = field(default_factory=Motion)
    speaking: bool = False
    picture: bytes = field(default_factory=room)
    grabs: int = 0

    def grab(self):
        self.grabs += 1
        return Frame(self.picture)


@dataclass
class Seer:
    people: bool = False
    asked: int = 0

    def find(self, frame, what):
        assert what == "person"
        self.asked += 1
        return [Mask(0.9)] if self.people else []


@dataclass
class Andy:
    now: float = 0.0
    _last_turn: float = float("-inf")
    following: bool = False
    playing: bool = False
    filming: dict | None = None
    body: Body = field(default_factory=Body)
    segmenter: Seer = field(default_factory=Seer)

    def clock(self):
        return self.now


@dataclass
class Loop:
    busy: bool = False
    awake_until: float = float("-inf")


@dataclass
class Ears:
    active: bool = False


def setup(**kw):
    andy, loop, ears, lines = Andy(**kw), Loop(), Ears(), []
    return Rest(woke_at=0.0), andy, loop, ears, lines


def look(rest, andy, loop, ears, lines):
    check(rest, andy, loop, ears, log=lines.append, monotonic=lambda: 0.0)


def test_after_ten_minutes_andy_rests_and_a_still_room_costs_no_sam():
    rest, andy, loop, ears, lines = setup()
    andy.now = REST_AFTER_S - 3
    look(rest, andy, loop, ears, lines)
    assert not rest.resting
    andy.now = REST_AFTER_S
    look(rest, andy, loop, ears, lines)
    assert rest.resting and andy.body.motion.resting and lines == ["resting: no turn for 10 minutes"]
    for _ in range(100):  # five minutes of looks at an empty, still room
        andy.now += 3
        look(rest, andy, loop, ears, lines)
    assert andy.segmenter.asked == 0 and andy.body.grabs == 100 and rest.resting


def test_someone_coming_in_wakes_andy_and_the_breath_comes_back():
    rest, andy, loop, ears, lines = setup(now=REST_AFTER_S)
    look(rest, andy, loop, ears, lines)
    andy.now += 3
    look(rest, andy, loop, ears, lines)  # the room as it is
    andy.body.picture, andy.segmenter.people = room(person=True), True
    andy.now += 3
    look(rest, andy, loop, ears, lines)
    assert not rest.resting and not andy.body.motion.resting
    assert andy.segmenter.asked == 1
    assert lines[-1].startswith("awake (someone there) after 0 minutes resting: the picture changed 1 times")


def test_a_lamp_going_on_asks_sam_once_and_andy_keeps_resting():
    rest, andy, loop, ears, lines = setup(now=REST_AFTER_S)
    look(rest, andy, loop, ears, lines)
    andy.now += 3
    look(rest, andy, loop, ears, lines)
    andy.body.picture = room(light=60)
    for _ in range(10):
        andy.now += 3
        look(rest, andy, loop, ears, lines)
    assert rest.resting and andy.segmenter.asked == 1


@pytest.mark.parametrize("what", ["turn", "filming", "speaking", "following"])
def test_a_turn_filming_or_anything_andy_does_wakes_it(what):
    rest, andy, loop, ears, lines = setup(now=REST_AFTER_S)
    look(rest, andy, loop, ears, lines)
    assert rest.resting
    andy.now += 30
    if what == "turn":
        andy._last_turn = andy.now - 1
    elif what == "filming":
        andy.filming = {"since": andy.now, "takes": []}
    elif what == "speaking":
        andy.body.speaking = True  # a reminder, said
    else:
        andy.following = True
    look(rest, andy, loop, ears, lines)
    assert not rest.resting and not andy.body.motion.resting
    assert lines[-1].startswith("awake (a turn)" if what == "turn" else "awake (busy)")


def test_never_rests_while_someone_is_talking_or_filming():
    for kw in ({"filming": {"since": 0, "takes": []}}, {}):
        rest, andy, loop, ears, lines = setup(now=REST_AFTER_S * 2, **kw)
        ears.active = not kw
        look(rest, andy, loop, ears, lines)
        assert not rest.resting and lines == []


def test_a_glance_round_the_room_is_left_alone():
    rest, andy, loop, ears, lines = setup(now=REST_AFTER_S)
    look(rest, andy, loop, ears, lines)
    andy.body.motion.set_mode("searching")
    andy.body.picture = room(person=True)
    andy.now += 3
    look(rest, andy, loop, ears, lines)
    assert rest.resting and andy.body.grabs == 0 and andy.segmenter.asked == 0


# --- the breath ---

def run(m, t0, t1, step=0.02):
    poses, t = [], t0
    while t <= t1:
        poses.append(m.pose(t, Pose()))
        t += step
    return poses


def test_resting_fades_the_breath_out_and_waking_brings_it_back_smoothly():
    m = Motion()
    run(m, 0, 5)
    m.resting = True
    fading = run(m, 5.02, 5.0 + REST_FADE_S + 0.5)
    still = run(m, 8.0, 20.0)
    assert all(p.pitch == pytest.approx(0.0) and p.z == pytest.approx(0.0) for p in still)
    assert len({p.antennas for p in still}) == 1  # the antennas hold: no motor turning back
    m.resting = False
    back = run(m, 20.02, 30.0)
    pitches = [p.pitch for p in fading + back]
    assert max(abs(a - b) for a, b in zip(pitches, pitches[1:])) < 0.05  # no jump, either way
    assert max(p.pitch for p in back[-250:]) == pytest.approx(m.breathe_pitch, abs=0.05)


def test_resting_leaves_the_turns_own_body_language_alone():
    m = Motion()
    m.resting = True
    run(m, 0, 5)
    m.set_mode("listening")
    poses = run(m, 5.02, 6.5)
    assert poses[-1].antennas[1] > Motion().pose(0, Pose()).antennas[1] + 0.15  # still spreads to listen
