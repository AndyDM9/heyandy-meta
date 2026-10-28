"""The cup game: the person hides a ball under one of a few cups and shuffles them; Andy says which cup it's under.

Identical cups crossing over each other are what per-frame finding can't follow: after the swap, which red cup is
which? SAM 3.1's Object Multiplex tracks every cup through the clip at once, each keeping its own identity. It runs
at about 5 frames a second here, slower than the camera, so Andy records the shuffle and replays it:

1. watch for the ball, a few times a second, until it disappears (under a cup);
2. record every camera frame (10 a second; half that loses the cups mid-swap) until the cups have moved and then
   stayed still for a moment, the person says "done", or 14 seconds pass;
3. replay the clip through SAM 3.1 on this computer: the cup nearest the ball just after it vanished is the one;
4. point at where that cup ended up.

Frames are held in memory for one game and dropped after it. Only the last one stays, for the TV, like a found thing.
"""
import math
import threading
import time
from dataclasses import dataclass, field

from ..finder.geometry import LITE, pixel_to_angles
from ..models.sam_local import Track

FPS = 10.0
MAX_SHUFFLE_S = 14.0
MAX_CLIP = 150  # frames sent to the tracker (local/sam_server.py takes up to 160)
SETTLE_AFTER = 5  # frames after the ball vanished at which the cup over it is judged (half a second)


@dataclass
class Result:
    how: str  # found | lost | no_cups | no_ball | not_hidden | stopped
    frame: object = None  # the clip's last frame, for the TV
    tracks: list = field(default_factory=list)
    chosen: object = None  # the Track the ball is under
    yaw: float = 0.0
    pitch: float = 0.0
    frames: int = 0  # frames replayed
    seconds: float = 0.0  # how long the replay took


class Clip:
    """The camera's frames as they come, in memory only, for one game."""

    def __init__(self, grab, max_frames: int, fps: float = FPS, clock=time.monotonic, sleep=time.sleep):
        self.frames: list = []
        self._grab, self._max, self._gap, self._clock, self._sleep = grab, max_frames, 1.0 / fps, clock, sleep
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "Clip":
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.is_set() and len(self.frames) < self._max:
            t = self._clock()
            try:
                self.frames.append(self._grab())
            except Exception:  # noqa: BLE001 - a missed frame; the camera comes back
                pass
            self._sleep(max(0.0, self._gap - (self._clock() - t)))

    def latest(self, after: int = -1, wait_s: float = 2.0):
        """The newest frame's index and the frame, once there's one newer than ``after``."""
        end = self._clock() + wait_s
        while len(self.frames) - 1 <= after and self._clock() < end and self._thread.is_alive():
            self._sleep(0.02)
        i = len(self.frames) - 1
        return (i, self.frames[i]) if i > after else (after, None)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    @property
    def full(self) -> bool:
        return len(self.frames) >= self._max


def look(segmenter, frame, things: list[str], min_score: float = 0.4) -> dict:
    many = getattr(segmenter, "find_many", None)
    found = many(frame, things) if many else {t: segmenter.find(frame, t) for t in things}
    return {t: [m for m in found.get(t, []) if m.score is None or m.score >= min_score] for t in things}


def moved(before: list, now: list, px: float) -> bool:
    """Did any cup move more than ``px`` between two looks? A different count means hands are in the way: moving."""
    if len(before) != len(now):
        return True
    return any(min(math.dist(a, b) for b in before) > px for a in now)


def at(track, frame: int) -> tuple[float, float] | None:
    """Where a tracked thing was at (or nearest before or after) a frame."""
    if not track.path:
        return None
    _, x, y = min(track.path, key=lambda p: (abs(p[0] - frame), p[0] > frame))
    return x, y


def stitch(tracks: list, near: float, max_gap: int = 6) -> list:
    """Two cups crossing can make SAM 3.1 drop one and find it again a moment later under a new id. A track that ends
    before the clip does is joined to one that starts within ``max_gap`` frames, near where it was heading."""
    order = sorted((t for t in tracks if t.path), key=lambda t: t.path[0][0])
    taken, out = set(), []
    for t in order:
        if t.id in taken:
            continue
        path, cur = list(t.path), t
        while cur.end is None:
            f, x, y = path[-1]
            g, px, py = path[max(0, len(path) - 4)]
            vx, vy = ((x - px) / (f - g), (y - py) / (f - g)) if f > g else (0.0, 0.0)
            best, nxt = near, None
            for c in order:
                s = c.path[0]
                if c.id in taken or c is t or not f - 3 <= s[0] <= f + max_gap:
                    continue
                k = max(0, s[0] - f)
                d = math.dist((x + vx * k, y + vy * k), s[1:])
                if d < best:
                    best, nxt = d, c
            if nxt is None:
                break
            taken.add(nxt.id)
            path += [p for p in nxt.path if p[0] > f]
            cur = nxt
        out.append(Track(cur.id, path, cur.end))
    return out


def under(tracks: list, ball: tuple[float, float], frame: int, within: float):
    """The cup the ball went under: the one nearest where the ball was last seen, just after it vanished."""
    near = [(math.dist(p, ball), t) for t in tracks if (p := at(t, frame)) is not None]
    near = [(d, t) for d, t in near if d <= within]
    return min(near, key=lambda n: n[0])[1] if near else None


def play(body, segmenter, track, stop, status=lambda what, **info: None, *, max_shuffle_s: float = MAX_SHUFFLE_S,
         ball_wait_s: float = 20.0, fps: float = FPS, clock=time.monotonic, sleep=time.sleep) -> Result:
    """One round, from "show me the ball" to where the ball is. ``track(frames, "cup")`` is SAM 3.1 Multiplex;
    ``stop()`` says the person called it off (or said "done" while shuffling); ``status`` tells the TV each stage."""
    grab = getattr(body, "grab", body.capture)
    clip = Clip(grab, max_frames=int((ball_wait_s + max_shuffle_s) * fps) + 20, fps=fps, clock=clock, sleep=sleep).start()
    try:
        return _play(clip, segmenter, track, stop, status, max_shuffle_s, ball_wait_s, clock)
    finally:
        clip.stop()
        clip.frames.clear()  # the clip is gone with the game


def _play(clip, segmenter, track, stop, status, max_shuffle_s, ball_wait_s, clock) -> Result:
    started, i, ball, misses, cups = clock(), -1, None, 0, 0
    status("ball")
    while True:  # 1. the ball, until it disappears under a cup
        if stop():
            return Result("stopped")
        if clock() - started > ball_wait_s:
            return Result("no_cups" if cups < 2 else "no_ball" if ball is None else "not_hidden")
        i, frame = clip.latest(i)
        if frame is None:
            continue
        seen = look(segmenter, frame, ["ball", "cup"])
        cups = max(cups, len(seen["cup"]))
        if seen["ball"]:
            if ball is None:
                status("seen")
            ball, misses = (i, max(seen["ball"], key=lambda m: m.score or 0.5).center), 0
        elif ball is not None and cups >= 2:
            misses += 1
            if misses >= 2:
                break
    hid, where = ball
    status("shuffling")
    hidden_at, before, moving, still_since = clock(), None, False, None
    px = 0.008 * frame.width
    while not stop() and clock() - hidden_at < max_shuffle_s and len(clip.frames) - hid < MAX_CLIP:  # 2. the shuffle
        i, frame = clip.latest(i)
        if frame is None:
            continue
        seen = look(segmenter, frame, ["cup", "hand"])
        now = [m.center for m in seen["cup"]]
        if before is not None and moved(before, now, px):
            moving, still_since = True, None
        elif before is not None:
            still_since = still_since or clock()
        before = now
        if still_since is not None:
            settled = clock() - still_since
            if (moving and settled >= (1.0 if not seen["hand"] else 2.5)) or (not moving and settled >= 4.0):
                break
    clip.stop()
    frames = clip.frames[hid:hid + MAX_CLIP]
    status("replaying", frames=len(frames))
    t = clock()
    tracks = track(frames, "cup")
    last = frames[-1]
    result = Result("lost", last, tracks, frames=len(frames), seconds=clock() - t)
    tracks = result.tracks = stitch(tracks, near=0.08 * last.width)
    chosen = under(tracks, where, min(SETTLE_AFTER, len(frames) - 1), within=0.15 * last.width)
    if chosen is None or chosen.end is None:
        return result
    cam = LITE.scaled(last.width, last.height)
    result.how, result.chosen = "found", chosen
    result.yaw, result.pitch = pixel_to_angles(*chosen.end.center, last.yaw, last.pitch, cam)
    return result
