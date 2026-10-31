"""Where a thing is from the person's side, not Andy's: "behind you, on your left, about 4 steps from you".

Andy says where it found a thing from where it sits ("a little to my right"), and someone facing Andy has to mirror it
(Andy's right is their left) and guess the distance from themselves. With the person's place (SAM 3.1 finds them,
MapAnything says how far: app.py _measure_listener) and the thing's (the find's direction, and MapAnything's
distance), both on a floor plan around Andy, and the person facing Andy (they're talking to it), the thing's bearing
and distance from the person follow, and are said the way people give directions, with a clock position as people
with low vision are often given them. Pure maths.
"""
import math

STEP_M = 0.7  # an unhurried step


def on_plan(yaw: float, pitch: float, metres: float) -> tuple[float, float]:
    """A direction from Andy's camera (degrees: yaw left positive, pitch down positive) and a distance, on the floor
    plan around Andy, seen from above: x to Andy's right, y ahead of Andy, metres."""
    flat = metres * math.cos(math.radians(pitch))
    return -flat * math.sin(math.radians(yaw)), flat * math.cos(math.radians(yaw))


def from_them(person: tuple[float, float, float], thing: tuple[float, float, float]) -> dict | None:
    """The thing from the person's side. person, thing: (yaw, pitch, metres) from Andy's camera. None if the person is
    too close to Andy to tell which way they face."""
    px, py = on_plan(*person)
    tx, ty = on_plan(*thing)
    near = math.hypot(px, py)
    if near < 0.3:
        return None
    fx, fy = -px / near, -py / near  # they face Andy
    rx, ry = fy, -fx  # and their right is a quarter turn clockwise from that, seen from above
    vx, vy = tx - px, ty - py
    ahead, right = vx * fx + vy * fy, vx * rx + vy * ry
    bearing = math.degrees(math.atan2(right, ahead))  # 0: in front of them; positive: to their right
    metres = math.hypot(vx, vy)
    return {"bearing": round(bearing, 1), "metres": round(metres, 2), "clock": round(bearing / 30) % 12 or 12,
            "andy_m": round(near, 2),  # Andy is straight ahead of them, this far
            "words": words(bearing, metres),
            "plan": {"you": [round(px, 2), round(py, 2)], "thing": [round(tx, 2), round(ty, 2)]}}


def side_of(bearing: float) -> str:
    a, hand = abs(bearing), "right" if bearing > 0 else "left"
    if a <= 25:
        return "in front of you"
    if a <= 65:
        return f"ahead of you, on your {hand}"
    if a <= 115:
        return f"on your {hand}"
    if a <= 155:
        return f"behind you, on your {hand}"
    return "behind you"


def words(bearing: float, metres: float) -> str:
    """"behind you, on your left, about 4 steps from you"; "right beside you" within an arm's reach."""
    if metres < 0.6:
        return "right beside you"
    steps = max(1, round(metres / STEP_M))
    return f"{side_of(bearing)}, about {steps} step{'s' if steps != 1 else ''} from you"
