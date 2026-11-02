"""Andy rests when nobody's there: still and quiet, its models idle, until someone comes or speaks to it.

November 2 (docs/research.md section 89): between moves Andy breathes (robot/motion.py), and its microphones heard its
own motors turn back, twice a breath, all night: 1,043 sounds an hour with nobody there, each heard by Omnilingual ASR
and each starting SAM 3.1's look for a face, so GPU 1 never rested (135 W, against 18 W resting). So after a while with
no turn, Andy rests: the breath fades out and the motors fall quiet. While it rests, SAM 3.1 is asked only when the
camera's picture changes: the head being still, a changed picture is the room changing (compared on the processor, at
160 by 90 in grey, and never kept). Someone there wakes it; so does any turn, filming, or a reminder (it speaks).
"""
import io
import time
from dataclasses import dataclass, field

from PIL import Image, ImageChops

SMALL = (160, 90)
CHANGED = 28  # a pixel this much brighter or darker (of 255) has changed: memory/notice.py's measure
LEAST = 0.002  # this share of the picture changed (29 of its 14,400 pixels): something in the room moved
REST_AFTER_S = 10 * 60
SAME_WAY = 0.5  # degrees: a picture taken with the head turned more than this is of another view, not a change


def grey(image: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image)).convert("L").resize(SMALL)


def changed_share(a: Image.Image, b: Image.Image) -> float:
    """The share of the picture that changed between two small grey pictures."""
    diff = ImageChops.difference(a, b).point(lambda v: 255 if v > CHANGED else 0)
    return diff.histogram()[255] / (SMALL[0] * SMALL[1])


@dataclass
class Rest:
    after_s: float = REST_AFTER_S
    resting: bool = False
    since: float = 0.0  # when this rest began
    woke_at: float = float("-inf")  # when Andy last woke (a rest starts again only after_s after it)
    looks: int = 0  # times SAM 3.1 was asked while resting: the picture had changed
    still: int = 0  # times the picture was compared and hadn't changed: SAM 3.1 not asked
    _ref: Image.Image | None = field(default=None, repr=False)
    _way: tuple[float, float] | None = None

    def due(self, now: float, last_turn: float, busy: bool) -> bool:
        """Time to rest: not already, nothing going on, and no turn (or waking) for after_s."""
        return (not self.resting and not busy and self.after_s != float("inf")  # --no-rest: never
                and now - max(last_turn, self.woke_at) >= self.after_s)

    def begin(self, now: float) -> None:
        self.resting, self.since, self._ref, self._way = True, now, None, None

    def wake(self, now: float) -> None:
        self.resting, self.woke_at, self._ref, self._way = False, now, None, None

    def changed(self, image: bytes, yaw: float, pitch: float) -> bool:
        """Has the room changed since the rest began, or since SAM last looked and found nobody? The first picture (the
        breath has faded by then), and one with the head turned another way (a glance round the room, a reminder), is
        what the room looks like now: not a change."""
        now = grey(image)
        if self._ref is None or self._way is None or max(abs(yaw - self._way[0]), abs(pitch - self._way[1])) > SAME_WAY:
            self._ref, self._way = now, (yaw, pitch)
            return False
        if changed_share(self._ref, now) < LEAST:
            self.still += 1
            return False
        self.looks += 1
        return True

    def nobody(self, image: bytes, yaw: float, pitch: float) -> None:
        """SAM looked and found nobody: the changed picture is the room now (a light went on, a curtain moved)."""
        self._ref, self._way = grey(image), (yaw, pitch)


def check(rest: Rest, andy, loop, ears, log=lambda line: print(line, flush=True), monotonic=time.monotonic) -> None:
    """One look, every few seconds: begin resting, wake, or (resting) compare the picture and, if it changed, ask SAM
    3.1 whether someone's there. The journal gets when and why, and how often SAM was asked: never a picture."""
    now = andy.clock()
    doing = (loop.busy or monotonic() <= loop.awake_until or andy.following or andy.playing or andy.filming
             or getattr(andy.body, "speaking", False))
    if not rest.resting:
        if rest.due(now, andy._last_turn, doing or ears.active or andy.body.motion.mode != "idle"):
            rest.begin(now)
            andy.body.motion.resting = True
            log(f"resting: no turn for {rest.after_s / 60:.0f} minutes")
        return
    if doing or andy._last_turn >= rest.since:
        _wake(rest, andy, "a turn" if andy._last_turn >= rest.since else "busy", log)
        return
    if andy.body.motion.mode != "idle":
        return  # a glance round the room for watched things: the picture is the glance's
    frame = andy.body.grab()
    if not rest.changed(frame.image, frame.yaw, frame.pitch):
        return
    if any((m.score or 0.0) >= 0.5 for m in andy.segmenter.find(frame, "person")):
        _wake(rest, andy, "someone there", log)
    else:
        rest.nobody(frame.image, frame.yaw, frame.pitch)


def _wake(rest: Rest, andy, why: str, log) -> None:
    now = andy.clock()
    minutes, looks, still = (now - rest.since) / 60, rest.looks, rest.still
    rest.wake(now)
    rest.looks = rest.still = 0
    andy.body.motion.resting = False
    log(f"awake ({why}) after {minutes:.0f} minutes resting: the picture changed {looks} times (SAM 3.1 asked), "
        f"{still} unchanged")
