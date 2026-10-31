"""Guide my hand: "Andy, help me reach it."

"Ahead of you, on your left, about 2 steps" brings someone who can't see well to the table; the last half metre is
where a hand sweeps about and knocks the mug over. So Andy keeps its eyes on the thing, watches for the person's hand
(SAM 3.1: the thing and "hand" from one encoding of each frame, a couple of times a second on this computer), and talks
the hand in from the person's side: "Left.", "Further.", "A little toward you.", with a soft note between the words
that rises as the hand gets nearer, like a parking sensor; then "That's it", when the hand is on it.

Where things are on the table, from one camera: the thing's distance was measured at the find (MapAnything), and with
it how far the camera is above the surface the thing is on (metres x sin pitch). A hand just over that surface, seen
at some pitch, is then about height / sin(pitch) away. Both go on the floor plan (finder/perspective.py on_plan), and
the way from the hand to the thing is turned to the person's side: they face Andy, so their left is Andy's right.
Pure maths, but for the loop at the end.
"""
import math
import time
from dataclasses import dataclass

from ..finder.geometry import LITE, pixel_to_angles
from ..finder.perspective import on_plan

HAND = "hand"
THERE_M = 0.08  # the hand's middle this close to the thing's middle (a palm beside a mug, on keys): it's there
COVERED = 0.3  # or the hand's box over this much of the thing's: there too (a hand over a thing sits above its plane)
LITTLE_M = 0.15  # nearer than this: "A little left."
NEAR_M = 0.5  # the notes start rising inside this
TABLE_M = 0.22  # the camera's height above the table, when the thing's distance wasn't measured (Andy on the table)
SAY_EVERY_S = 2.5  # the same words again after this long; new words at once
HAND_SCORE = 0.4  # a hand is only a hand this sure (a glove on the table isn't someone reaching)


def height_above(pitch: float, metres: float | None) -> float:
    """How far the camera is above the surface a thing seen at this pitch (down positive) and distance sits on."""
    if metres is None or pitch < 3:
        return TABLE_M
    return max(0.05, metres * math.sin(math.radians(pitch)))


def on_surface(yaw: float, pitch: float, height: float) -> tuple[float, float]:
    """A point seen at (yaw, pitch) on the floor plan (x to Andy's right, y ahead), if it's on a surface `height`
    below the camera. Near the horizon it's taken as about as far as a table reaches."""
    metres = height / math.sin(math.radians(max(pitch, 4.0)))
    return on_plan(yaw, pitch, metres)


def their_way(person: tuple[float, float], hand: tuple[float, float], thing: tuple[float, float]) -> tuple[float, float]:
    """From the hand to the thing, on the person's side: (to their right, further from them), in metres. The person,
    on the plan, faces Andy."""
    near = math.hypot(*person) or 1.0
    fx, fy = -person[0] / near, -person[1] / near  # they face Andy
    rx, ry = fy, -fx  # their right: a quarter turn clockwise from that, seen from above
    vx, vy = thing[0] - hand[0], thing[1] - hand[1]
    return vx * rx + vy * ry, vx * fx + vy * fy


def instruction(right: float, further: float) -> str:
    """What to say to move the hand: "Left.", "Further, and right.", "A little toward you.", or "" when it's there."""
    d = math.hypot(right, further)
    if d <= THERE_M:
        return ""
    side, depth = "right" if right > 0 else "left", "further" if further > 0 else "toward you"
    a, b = abs(right), abs(further)
    words = side if a >= 2 * b else depth if b >= 2 * a else f"{depth}, and {side}"
    return ("A little " + words if d < LITTLE_M else words[0].upper() + words[1:]) + "."


def note(metres: float) -> str:
    """The soft note between the words (voice/earcons.py): near1 far off, up to near5 at the thing."""
    return f"near{1 + min(4, int((1 - min(metres, NEAR_M) / NEAR_M) * 5))}"


def covered(hand: tuple, thing: tuple) -> float:
    """How much of the thing's box the hand's box covers, 0-1 (boxes: left, top, right, bottom)."""
    w = min(hand[2], thing[2]) - max(hand[0], thing[0])
    h = min(hand[3], thing[3]) - max(hand[1], thing[1])
    area = max(1, (thing[2] - thing[0]) * (thing[3] - thing[1]))
    return max(0, w) * max(0, h) / area


# The words in Spanish, so a guide in Spanish needs no translation between frames (companion/language.py PHRASES)
_SIDE_ES = {"left": "a la izquierda", "right": "a la derecha"}
_DEPTH_ES = {"further": "más lejos", "toward you": "hacia usted"}


def _spanish() -> dict[str, str]:
    out = {}
    for en, es in [*_SIDE_ES.items(), *_DEPTH_ES.items(),
                   *((f"{d}, and {s}", f"{de}, y {se}") for d, de in _DEPTH_ES.items() for s, se in _SIDE_ES.items())]:
        out[en[0].upper() + en[1:] + "."] = es[0].upper() + es[1:] + "."
        out[f"A little {en}."] = f"Un poco {es}."
    return out


ES = _spanish()


@dataclass
class Guided:
    why: str  # "there": the hand is on it; "no hand": none seen; "lost": the thing went out of sight; "stopped"; "time"
    frames: int
    closest: float | None  # metres: the nearest the hand came


def guide(body, segmenter, thing: str, start: tuple[float, float], height: float, person: tuple[float, float],
          say, sound, on_frame, stop, seconds: float = 40.0, cam=lambda frame: LITE, every: float = 0.4,
          min_score: float = 0.3, lose_after: int = 6, clock=time.monotonic, wait=time.sleep) -> Guided:
    """Talk the hand onto the thing. start: where the thing is (yaw, pitch); height: the camera above its surface;
    person: where they are on the plan. say(words) speaks, sound(name) plays a note, on_frame(frame, thing_mask,
    hand_mask, words, way, metres) shows it (way: degrees on their side, 0 further from them, 90 to their right)."""
    last, frames, missing, closest, near = start, 0, 0, None, None
    said, said_at, seen_hand = "", -1e9, False
    waiting_at = clock()  # the app has just said to put a hand out
    deadline = waiting_at + seconds
    while not stop():
        began = clock()
        if began >= deadline:
            return Guided("time" if seen_hand else "no hand", frames, closest)
        frame = body.capture()
        frames += 1
        c = cam(frame)
        found = _find(segmenter, frame, [thing, HAND])
        at = {id(m): pixel_to_angles(*m.center, frame.yaw, frame.pitch, c) for ms in found.values() for m in ms}
        things = [m for m in found.get(thing, []) if m.score is None or m.score >= min_score]
        hands = [m for m in found.get(HAND, []) if m.score is None or m.score >= HAND_SCORE]
        mask = min(things, key=lambda m: math.dist(at[id(m)], last)) if things else None
        hand = min(hands, key=lambda m: math.dist(at[id(m)], last)) if hands else None  # the one reaching, not one resting
        if mask is None:
            missing += 1
            if hand is not None and near is not None and near <= LITTLE_M:  # the hand reaching it now covers it
                on_frame(frame, None, hand, "", None, 0.0)
                return Guided("there", frames, 0.0)
            if missing >= lose_after:
                return Guided("lost", frames, closest)
            _rest(clock, wait, began, every)
            continue
        missing, last = 0, at[id(mask)]
        if hand is None:
            on_frame(frame, mask, None, "", None, None)
            if began - waiting_at >= 8.0:  # now and then, never over the words
                say("I can't see your hand.")
                waiting_at = clock()
            _rest(clock, wait, began, every)
            continue
        seen_hand, waiting_at = True, began
        right, further = their_way(person, on_surface(*at[id(hand)], height), on_surface(*last, height))
        near = 0.0 if covered(hand.box, mask.box) >= COVERED else math.hypot(right, further)
        closest = near if closest is None else min(closest, near)
        words = instruction(right, further) if near > 0 else ""
        on_frame(frame, mask, hand, words, round(math.degrees(math.atan2(right, further))), near)
        if not words:
            return Guided("there", frames, closest)
        if words != said or began - said_at >= SAY_EVERY_S:
            say(words)
            said, said_at = words, clock()
        else:
            sound(note(near))
        _rest(clock, wait, began, every)
    return Guided("stopped", frames, closest)


def _find(segmenter, frame, queries: list[str]) -> dict:
    many = getattr(segmenter, "find_many", None)
    return many(frame, queries) if many else {q: segmenter.find(frame, q) for q in queries}


def _rest(clock, wait, began: float, every: float) -> None:
    left = every - (clock() - began)
    if left > 0:
        wait(left)
