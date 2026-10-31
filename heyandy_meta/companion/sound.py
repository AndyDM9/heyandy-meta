"""Find it by sound: "Hey Andy, I'm ringing my phone."

A phone under a cushion is invisible to a camera, but it can ring, and a tracker on a key ring can chirp. The robot's
microphone array says which side a sound comes from (Pollen's DoA; robot/reachy_mini.py listen), so Andy turns its
head towards the ringing until the array hears it straight ahead, the way a person turns to a sound, then looks with
SAM 3.1 only around that way. If it still can't see it, it points where the sound is: "I can hear it, but I can't
see it. It's ringing over there."

Why turn rather than read the angle once: on the robot (2026-10-31, evals/sound.py) the array's angle followed a
fixed ringtone by only 0.2 to 0.45 degrees for each degree the head turned. One reading says which side, reliably,
but not how far; where the array hears the sound straight ahead is where the sound is.

What counts as ringing: chunks (about 0.1 s each) much louder than the room's own noise, most of them tonal, as a
ringtone or a chirp is and a voice isn't (spectral flatness: a pure tone near 0, noise near 1; measured on the robot,
the loud chunks of two ringtones 0.000 to 0.008, of a spoken sentence 0.004 to 0.18, median 0.03 to 0.06), and with
a direction from the array. Nothing is recorded: per chunk only its loudness, its flatness and its direction are kept,
for 20 seconds.
"""
import math
import time
from collections import deque

import numpy as np

RATE = 16000
TONAL = 0.015  # spectral flatness at or below this is a tone
TONAL_SHARE = 0.6  # of the loud chunks, at least this many must be tones: a voice is tonal only now and then
LOUDER = 4.0  # times the room's noise floor
QUIET_FLOOR = 0.004  # a floor for very quiet rooms, so a click isn't "four times louder"
ENOUGH = 4  # ringing chunks with a side for one reading (a reading listens about 1.6 s: two rings or more)
AHEAD_DEG = 1.0  # a reading this small says nothing about the side (within about 20 degrees of the sound)
STEP_DEG = 40.0  # a turn towards the side heard, until the sound is between two turns
BRACKET_DEG = 30.0  # placed once the nearest clear left and clear right are this close: the middle is the sound
NARROW_DEG = BRACKET_DEG / 2  # how far from the sound the middle can be, at most, when the blind band is even
TURNS = 8  # at most
WAIT_S = 30.0  # how long Andy waits for the ringing to start


def flatness(samples: np.ndarray, rate: int = RATE) -> float:
    """Spectral flatness over 300 Hz to 5 kHz: the geometric over the arithmetic mean of the power. 0: a pure tone."""
    x = np.asarray(samples, dtype=np.float64)
    if len(x) < 64:
        return 1.0
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / rate)
    band = p[(f >= 300) & (f <= 5000)] + 1e-12
    return float(np.exp(np.mean(np.log(band))) / np.mean(band))


class Ear:
    """The last few seconds the microphones heard, as numbers: (when, loudness, flatness, side) per chunk, where side
    is how many degrees left of where the head looks the array put the sound (compressed, so a side more than an
    angle), or None. The voice loop fills it as it listens (voice/loop.py run); a turn reads it."""

    def __init__(self, head=lambda: 0.0, seconds: float = 20.0, clock=time.monotonic):
        self.head, self.clock, self.seconds = head, clock, seconds
        self._chunks: deque = deque()

    def __call__(self, samples, flag: bool, yaw: float | None) -> None:
        x = np.asarray(samples, dtype=np.float32)
        now = self.clock()
        side = (yaw - self.head()) if flag and yaw is not None else None
        self._chunks.append((now, float(np.sqrt(np.mean(x * x))) if len(x) else 0.0, flatness(x), side))
        while self._chunks and now - self._chunks[0][0] > self.seconds:
            self._chunks.popleft()

    def since(self, t: float) -> list[tuple]:
        return [c for c in list(self._chunks) if c[0] >= t]

    def floor(self) -> float:
        """The room's own noise: a low percentile of everything heard lately."""
        levels = sorted(c[1] for c in self._chunks)
        return max(levels[len(levels) // 5] if levels else 0.0, QUIET_FLOOR)


def ringing(chunks: list[tuple], floor: float) -> list[tuple]:
    """The chunks that are a ringing: loud, tonal (most of the loud ones must be), with a side. [] if it isn't one."""
    loud = [c for c in chunks if c[1] >= LOUDER * max(floor, QUIET_FLOOR)]
    tones = [c for c in loud if c[2] <= TONAL]
    if not loud or len(tones) < TONAL_SHARE * len(loud):
        return []
    with_side = [c for c in tones if c[3] is not None]
    return with_side if len(with_side) >= ENOUGH else []


def reading(chunks: list[tuple], floor: float) -> float | None:
    """Which side of the head the ringing is on, in the array's (compressed) degrees: positive left. None: no ringing."""
    r = ringing(chunks, floor)
    return float(np.median([c[3] for c in r])) if r else None


def wait_for(listen, seconds: float = WAIT_S, each: float = 1.6, on_wait=None) -> bool:
    """Until a ringing starts: the person dials after Andy says "ring it now", and that takes a while (another phone
    found, the number chosen). listen() hears for `each` seconds; True as soon as one hears a ringing."""
    for i in range(max(1, int(seconds / each))):
        if on_wait:
            on_wait(round(seconds - i * each))
        if listen() is not None:
            return True
    return False


def turn_to(listen, turn, start: float, reach=(-150.0, 150.0), on_step=None) -> tuple[float | None, list]:
    """Turn the head towards a ringing, by the side heard only: the array's angle is too compressed to say how far,
    and within about 20 degrees of the sound it reads near zero either way (see above). So zeros say little; what
    places the sound is the nearest yaw it's clearly left of and the nearest it's clearly right of: the sound is
    between, in the middle. Turn STEP_DEG towards the side heard until there are both, then look between them where
    the gap is widest, until the two are BRACKET_DEG apart. listen() -> a reading at the head's yaw (None: no ringing);
    turn(yaw) moves the head. Returns (the yaw facing it, or None if nothing was heard; the steps [(yaw, reading)])."""
    steps, yaw = [], start
    for _ in range(TURNS):
        turn(yaw)
        side = listen()
        if side is None:
            side = listen()  # a gap between rings: once more
            if side is None:
                break
        steps.append((yaw, side))
        if on_step:
            on_step(yaw, side, steps)
        left = [y for y, s in steps if s > AHEAD_DEG]  # the sound is left of these yaws: it's at a larger one
        right = [y for y, s in steps if s < -AHEAD_DEG]
        lo, hi = (max(left) if left else None), (min(right) if right else None)
        zeros = [y for y, s in steps if abs(s) <= AHEAD_DEG]
        if lo is not None and hi is not None:
            if hi - lo <= BRACKET_DEG or lo >= hi:  # placed (or the readings disagree: settle between them)
                return (lo + hi) / 2, steps
            inside = sorted({lo, hi, *(y for y, _ in steps if lo < y < hi)})
            a, b = max(zip(inside, inside[1:]), key=lambda g: g[1] - g[0])
            if b - a <= BRACKET_DEG / 2:
                return (lo + hi) / 2, steps
            nxt = (a + b) / 2
        elif lo is not None:  # left of everything clearly: further left (in smaller steps once near it)
            nxt = max(y for y, _ in steps) + (STEP_DEG if not zeros else STEP_DEG / 2)
        elif hi is not None:
            nxt = min(y for y, _ in steps) - (STEP_DEG if not zeros else STEP_DEG / 2)
        else:  # only near-zeros: it's near here; look a little either side
            nxt = start + (STEP_DEG / 2 if len(steps) % 2 else -STEP_DEG / 2)
        nxt = min(max(nxt, reach[0]), reach[1])
        if any(abs(nxt - y) < 1.0 for y, _ in steps):
            break
        yaw = nxt
    if not steps:
        return None, steps
    left = [y for y, s in steps if s > AHEAD_DEG]
    right = [y for y, s in steps if s < -AHEAD_DEG]
    zeros = [y for y, s in steps if abs(s) <= AHEAD_DEG]
    if left and right:
        return (max(left) + min(right)) / 2, steps
    if zeros:
        return sum(zeros) / len(zeros), steps
    return (max(left) + STEP_DEG / 2) if left else (min(right) - STEP_DEG / 2), steps


def apart(a: float, b: float) -> float:
    """Degrees between two yaws, the short way round."""
    return abs((a - b + 180) % 360 - 180)


def fan(yaw: float) -> tuple:
    """Where to look for a thing heard at this yaw: that way first, low and high, then a little either side."""
    return ((yaw, 20.0), (yaw, 35.0), (yaw + 22.0, 25.0), (yaw - 22.0, 25.0), (yaw, 8.0))
