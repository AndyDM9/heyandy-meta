"""Body language between moves: the robot is never frozen.

A small set of layers, added on top of where the head was last sent (pointing at a thing, or facing the person):
- **breathing**, always (but resting: companion/rest.py): a slow rise and fall of the head and a mirrored sway of
  the antennas;
- **listening**: the antennas spread a little and hold, like attention;
- **thinking**: the antennas lean together to one side and back, and the head tilts, so a pause never looks dead;
- **speaking**: the head moves with Andy's own words (Pollen's wobbler supplies the offsets); the antennas swing
  with the nod;
- **found**: one happy wiggle of the antennas.

Each layer fades in and out over about half a second, so nothing jumps, and every amplitude stays well inside the
robot's limits. Searching switches all of it off: frames and pointing need a still head. This module is pure maths;
the Reachy adapter runs it in a loop and sends the result.
"""
import math
from dataclasses import dataclass, field

UPRIGHT = (-0.1745, 0.1745)  # antennas (right, left), radians: Pollen's resting position
MODES = ("idle", "listening", "thinking", "speaking", "searching")
FADE_S = 0.5
REST_FADE_S = 2.0  # the breath fades out this slowly when Andy rests, and back in when it wakes


@dataclass
class Pose:
    yaw: float = 0.0  # degrees, left positive
    pitch: float = 0.0  # degrees, down positive
    roll: float = 0.0  # degrees
    z: float = 0.0  # metres, up positive
    antennas: tuple[float, float] = UPRIGHT


@dataclass
class Motion:
    breathe_hz: float = 0.22  # about 13 breaths a minute
    breathe_pitch: float = 1.2  # degrees
    breathe_z: float = 0.002  # metres
    breathe_antennas: float = 0.06  # radians
    listen_spread: float = 0.25
    think_lean: float = 0.35
    think_roll: float = 6.0
    liveliness: float = 1.0  # "move less": every layer scaled down (older participants liked calmer motion: ELEGNT)
    mode: str = "idle"
    resting: bool = False  # nobody's been here a while (companion/rest.py): the breath fades out, the motors fall quiet
    speech: tuple = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # Pollen's wobbler: x, y, z (m), roll, pitch, yaw (rad)
    _weights: dict = field(default_factory=lambda: {m: 0.0 for m in MODES})
    _last_t: float | None = None
    _wiggle_until: float = 0.0
    _rest_w: float = 0.0

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        self.mode = mode

    def wiggle(self, now: float, seconds: float = 0.8) -> None:
        self._wiggle_until = now + seconds

    def _fade(self, now: float) -> dict:
        dt = 0.0 if self._last_t is None else max(0.0, min(0.2, now - self._last_t))
        self._last_t = now
        for m in MODES:
            target = 1.0 if m == self.mode else 0.0
            w = self._weights[m]
            step = dt / FADE_S
            self._weights[m] = min(target, w + step) if target > w else max(target, w - step)
        step = dt / REST_FADE_S
        self._rest_w = min(1.0, self._rest_w + step) if self.resting else max(0.0, self._rest_w - step)
        return self._weights

    def pose(self, now: float, base: Pose) -> Pose:
        """Where to send the head and antennas at time ``now``, around ``base``."""
        w = self._fade(now)
        k = self.liveliness
        alive = (1.0 - w["searching"]) * k * (1.0 - self._rest_w)  # resting: no breath, so no sound of motors
        phase = math.sin(2 * math.pi * self.breathe_hz * now)
        out = Pose(base.yaw, base.pitch + alive * self.breathe_pitch * phase, base.roll,
                   base.z + alive * self.breathe_z * phase, base.antennas)
        right, left = base.antennas
        b = alive * self.breathe_antennas * phase  # mirrored: both out, both in
        right, left = right - b, left + b
        spread = w["listening"] * self.listen_spread * k
        right, left = right - spread, left + spread
        lean = w["thinking"] * self.think_lean * k * math.sin(2 * math.pi * 0.35 * now)  # both to one side, slowly
        right, left = right + lean, left + lean
        out.roll += w["thinking"] * self.think_roll * k
        if w["speaking"]:
            x, y, z, roll, pitch, yaw = (v * k for v in self.speech)
            out.yaw += w["speaking"] * math.degrees(yaw)
            out.pitch += w["speaking"] * math.degrees(pitch)
            out.roll += w["speaking"] * math.degrees(roll)
            out.z += w["speaking"] * z
            swing = w["speaking"] * 4.0 * pitch
            right, left = right - swing, left + swing
        if now < self._wiggle_until:
            wag = 0.3 * k * math.sin(2 * math.pi * 3.0 * now)
            right, left = right + wag, left + wag
        out.antennas = (max(-1.2, min(0.6, right)), max(-0.6, min(1.2, left)))
        return out
