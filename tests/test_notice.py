import io

from PIL import Image, ImageDraw

from heyandy_meta.memory.notice import Noticer, moved
from heyandy_meta.memory.places import Places
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.body import Frame


def jpeg(square_at=None, shift=0) -> bytes:
    """A plain room in grey, with stripes (so a camera turn shows), and a dark square where a hand and a thing are."""
    im = Image.new("RGB", (1920, 1080), (150, 150, 150))
    d = ImageDraw.Draw(im)
    for x in range(0, 1920, 120):
        d.rectangle((x + shift, 0, x + shift + 50, 1080), fill=(110, 110, 110))
    if square_at:
        d.rectangle((square_at, 600, square_at + 120, 720), fill=(20, 20, 20))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92)
    return out.getvalue()


def test_moved_finds_where_something_moved_and_ignores_a_still_or_turning_view():
    still = [jpeg() for _ in range(4)]
    assert moved(still)[0] is None
    hand = [jpeg(square_at=800 + 20 * i) for i in range(4)]
    box, share = moved(hand)
    assert box is not None and 780 <= box[0] <= 820 and box[2] <= 1000 and 0.002 <= share <= 0.3
    turning = [jpeg(shift=40 * i) for i in range(4)]  # the head turning: the whole picture moves
    assert moved(turning)[0] is None


class Body:
    def __init__(self, images):
        self.images, self.i = images, 0

    def grab(self):
        self.i += 1
        return Frame(self.images[min(self.i - 1, len(self.images) - 1)], 1920, 1080, -20.0, 15.0)


class Seer:
    def __init__(self, put=0.0, taken=0.0, keys_at=None):
        self.put, self.taken, self.keys_at, self.asked = put, taken, keys_at, []

    def action(self, clip, box):
        self.asked.append(box)
        return {"put": self.put, "taken": self.taken, "top": []}

    def find_many(self, frame, names):
        keys = [Mask("keys", (self.keys_at - 40, 620, self.keys_at + 40, 700), 0.9, center=(self.keys_at, 660.0))] \
            if self.keys_at else []
        return {n: (keys if n == "keys" else []) for n in names}


def noticer(seer, images, tmp_path, watch=("keys",)):
    places = Places(tmp_path / f"places-{len(list(tmp_path.iterdir()))}.json")
    for w in watch:
        places.watch(w)
    return Noticer(Body(images), seer, places, sleep=lambda s: None, clock=lambda: 1000.0), places


def test_a_watched_thing_put_down_where_something_moved_gets_its_new_place(tmp_path):
    n, places = noticer(Seer(put=0.8, keys_at=880), [jpeg(square_at=800 + 5 * i) for i in range(16)], tmp_path)
    seen = n.watch_once()
    assert seen["kind"] == "put" and seen["things"] == ["keys"] and "keys" in seen["masks"]
    yaw, pitch = places.last_seen("keys", now=1000.0)
    assert -17 < yaw < -15 and 20 < pitch < 23  # a little left of the middle of a view at -20, below it: the keys


def test_nothing_is_asked_when_nothing_moved_or_nothing_is_watched(tmp_path):
    seer = Seer(put=0.9, keys_at=880)
    n, _ = noticer(seer, [jpeg() for _ in range(16)], tmp_path)
    assert n.watch_once() is None and seer.asked == []  # a still room: V-JEPA 2 isn't asked
    n, _ = noticer(seer, [jpeg(square_at=800 + 5 * i) for i in range(16)], tmp_path, watch=())
    assert n.watch_once() is None and seer.asked == []  # nothing watched: no watching at all


def test_movement_that_isnt_putting_down_changes_nothing(tmp_path):
    n, places = noticer(Seer(put=0.1, taken=0.05, keys_at=880), [jpeg(square_at=800 + 5 * i) for i in range(16)], tmp_path)
    assert n.watch_once() is None and places.last_seen("keys", now=1000.0) is None


def test_a_watched_thing_picked_up_from_where_it_was_is_noticed(tmp_path):
    n, places = noticer(Seer(taken=0.7), [jpeg(square_at=800 + 5 * i) for i in range(16)], tmp_path)
    places.saw("keys", -16.0, 21.4, when=990.0)  # last seen right where the hand moved
    seen = n.watch_once()
    assert seen["kind"] == "taken" and seen["things"] == ["keys"]


def test_a_turn_takes_the_head_back_from_a_noticing_clip(tmp_path):
    from heyandy_meta.robot.motion import Motion
    from tests.test_app import andy

    a, body, _ = andy(tmp_path=tmp_path)
    body.motion = Motion()
    cancel = a.begin_noticing()
    assert cancel is not None and body.motion.mode == "searching"
    a.hear("Good morning")  # a typed turn makes no gesture of its own
    assert cancel.is_set() and body.motion.mode == "idle"
    body.motion.set_mode("listening")  # the next turn's own body language
    a.end_noticing(cancel)
    assert body.motion.mode == "listening"  # the clip's end never overwrites it
    cancel = a.begin_noticing()
    a.end_noticing(cancel)
    assert body.motion.mode == "listening" and cancel is None  # not idle: no clip starts
    body.motion.set_mode("idle")
    import threading

    held, done = threading.Event(), threading.Event()

    def turn():  # a turn running on its own thread, as the voice loop runs them
        with a.lock:
            held.set()
            done.wait(2)

    running = threading.Thread(target=turn)
    running.start()
    held.wait(2)
    assert a.begin_noticing() is None
    done.set()
    running.join(2)
    cancel = a.begin_noticing()
    a.end_noticing(cancel)
    assert not cancel.is_set() and body.motion.mode == "idle"


def test_a_cancelled_clip_asks_no_model_and_changes_no_memory(tmp_path):
    seer = Seer(put=0.9, keys_at=880)
    n, places = noticer(seer, [jpeg(square_at=800 + 5 * i) for i in range(16)], tmp_path)
    calls = []
    assert n.watch_once(cancelled=lambda: calls.append(1) or len(calls) > 5) is None
    assert seer.asked == [] and places.last_seen("keys", now=1000.0) is None
