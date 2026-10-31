"""The Reachy Mini adapter: the only module that imports Pollen's SDK.

A direction is split between the head (up to ``head_yaw`` either way) and a turn of the base, sent as one smooth
move. Moves are slow enough to be gentle (about 70 degrees a second at most), and every direction is clamped to the
body's reach first.

Measured on the Lite (2026-10-27): the base turns where it's told (39.6 for 40 degrees), but the head falls short and
sags (asked for 55 it reached 40.5; asked for 0 it sat 2 to 5 degrees off). So the head takes only small turns, the
adapter reads back where the head really is after each move, corrects once if it's more than ``tolerance`` off,
and frames carry the measured direction, not the commanded one.
"""
import math
import struct
import threading
import time

from .body import Frame, Reach
from .motion import Motion, Pose


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Width and height from a JPEG's start-of-frame marker."""
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("not a JPEG with a frame header")


def _yaw_pitch(pose) -> tuple[float, float]:
    """Yaw (left positive) and pitch (down positive) in degrees from a 4x4 head pose."""
    return math.degrees(math.atan2(pose[1][0], pose[0][0])), math.degrees(math.asin(-max(-1.0, min(1.0, pose[2][0]))))


EMOTIONS = "pollen-robotics/reachy-mini-emotions-library"

class ReachyBody:
    def __init__(self, robot=None, reach: Reach = Reach(), head_yaw: float = 30.0, max_deg_s: float = 70.0,
                 settle_s: float = 0.3, tolerance: float = 1.5, pose=None, say=None, sleep=time.sleep,
                 alive: bool | None = None):
        alive = robot is None if alive is None else alive
        if robot is None:
            from reachy_mini import ReachyMini

            # Never media_backend="no_media": it makes the daemon release the camera and audio for everyone.
            robot = ReachyMini(automatic_body_yaw=False, connection_mode="localhost_only").__enter__()
        self._full_pose = None
        if pose is None:
            from reachy_mini.utils import create_head_pose

            self._full_pose = create_head_pose  # with x, y, z: for the speech-driven sway

            pose = lambda yaw, pitch, roll=0.0: create_head_pose(yaw=yaw, pitch=pitch, roll=roll, degrees=True)  # noqa: E731
        self.robot, self.reach, self.head_yaw, self.tolerance = robot, reach, head_yaw, tolerance
        self.max_deg_s, self.settle_s = max_deg_s, settle_s
        self._pose, self._say, self._sleep = pose, say, sleep
        self.yaw = self.pitch = 0.0  # where the head is looking, measured when the robot can tell us
        self.speaking = False  # Andy's voice is playing
        self._sent = (0.0, 0.0, 0.0)  # the last head yaw, pitch and base yaw sent
        self.motion = Motion()
        self._emotions = None  # Pollen's recorded emotions, loaded the first time one is played
        self._moving = threading.RLock()  # one sender at a time: a move, or the body-language loop
        self._gaze: tuple[float, float] | None = None  # a direction to ease the head towards (the person's face)
        self._stop = threading.Event()
        if alive and self._full_pose is not None:
            threading.Thread(target=self._live, daemon=True, name="body-language").start()

    def split(self, yaw: float) -> tuple[float, float]:
        """(head yaw, base yaw) for a direction: the head turns first, the base makes up the rest."""
        head = max(-self.head_yaw, min(self.head_yaw, yaw))
        return head, yaw - head

    def measured(self) -> tuple[float, float] | None:
        """Where the head really looks. The daemon's head pose is in the room's frame, the base's turn already in it
        (measured on the Lite, 2026-10-31: the same view with the base at 0 and at -30 degrees)."""
        if not hasattr(self.robot, "get_current_head_pose"):
            return None
        return _yaw_pitch(self.robot.get_current_head_pose())

    def _send(self, head: float, pitch: float, base: float, duration: float) -> None:
        """head is the head's turn on the body; the daemon takes the head's direction in the room, so the base's turn
        is added (sent alone, the head keeps facing the same way while the base turns under it)."""
        with self._moving:
            self.robot.goto_target(head=self._pose(head + base, pitch), body_yaw=math.radians(base), duration=duration)
            self._sent = (head, pitch, base)

    def _live(self, hz: float = 50.0) -> None:
        """The body-language loop: between moves, send the base pose plus Motion's layers, 50 times a second."""
        period = 1.0 / hz
        while not self._stop.is_set():
            start = time.monotonic()
            if self.motion.mode != "searching" and self._moving.acquire(blocking=False):
                try:
                    self._ease(period)
                    head, pitch, base = self._sent
                    p = self.motion.pose(start, Pose(yaw=head, pitch=pitch))
                    self.robot.set_target(head=self._full_pose(z=p.z, roll=p.roll, pitch=p.pitch, yaw=p.yaw + base, degrees=True),
                                          antennas=list(p.antennas), body_yaw=math.radians(base))
                except Exception:  # noqa: BLE001 - a dropped tick is harmless; the loop must not die
                    pass
                finally:
                    self._moving.release()
            time.sleep(max(0.0, period - (time.monotonic() - start)))

    def _ease(self, dt: float, max_deg_s: float = 40.0) -> None:
        """Turn the head smoothly towards the gaze direction, within the head's own range (the base stays)."""
        if self._gaze is None:
            return
        head, pitch, base = self._sent
        want = max(-self.head_yaw, min(self.head_yaw, self._gaze[0] - base))
        step = max_deg_s * dt
        head += max(-step, min(step, want - head))
        pitch += max(-step, min(step, self._gaze[1] - pitch))
        self._sent = (head, pitch, base)
        self.yaw, self.pitch = head + base, pitch

    def face(self, yaw: float, pitch: float) -> None:
        """Keep looking towards a direction (a person's face) without stopping the body language."""
        self._gaze = self.reach.clamp(yaw, pitch)

    def look(self, yaw: float, pitch: float, precise: bool = True) -> None:
        self._gaze = None
        yaw, pitch = self.reach.clamp(yaw, pitch)
        travel = max(abs(yaw - self.yaw), abs(pitch - self.pitch))
        head, base = self.split(yaw)
        self._send(head, pitch, base, max(0.6, travel / self.max_deg_s))
        self._sleep(self.settle_s)  # let the camera stop moving before a frame is read
        now = self.measured()
        if precise and now and max(abs(yaw - now[0]), abs(pitch - now[1])) > self.tolerance:
            # One correction, on the head only (the base is accurate), at most 15 degrees each way.
            fix = lambda err: max(-15.0, min(15.0, err))  # noqa: E731
            self._send(max(-60.0, min(60.0, head + fix(yaw - now[0]))), pitch + fix(pitch - now[1]), base, 0.4)
            self._sleep(self.settle_s)
            now = self.measured()
        self.yaw, self.pitch = now or (yaw, pitch)

    def _next_frame(self, wait_s: float = 2.0) -> bytes | None:
        """The camera hands over each frame once; wait briefly for a new one."""
        for _ in range(max(1, int(wait_s / 0.05))):
            data = self.robot.media.get_frame_jpeg()
            if data:
                return data
            self._sleep(0.05)
        return None

    def capture(self) -> Frame:
        stale = self._next_frame()  # this one may be from before the move finished
        data = self._next_frame(0.5) or stale
        if not data:
            raise RuntimeError("the camera returned no frame")
        now = self.measured()  # the head may still have been settling: say where it was for this frame
        if now:
            self.yaw, self.pitch = now
        w, h = jpeg_size(data)
        return Frame(data, w, h, self.yaw, self.pitch)

    def grab(self) -> Frame:
        """The next camera frame as it comes, without waiting for the head: for recording a clip with the head still."""
        data = self._next_frame(0.5)
        if not data:
            raise RuntimeError("the camera returned no frame")
        w, h = jpeg_size(data)
        return Frame(data, w, h, self.yaw, self.pitch)

    def point(self, yaw: float, pitch: float) -> None:
        """Point with the head: face the thing, dip once towards it, and hold."""
        self.look(yaw, pitch)
        head, sent_pitch, base = self._sent
        self._send(head, min(sent_pitch + 6.0, self.reach.pitch_down + 10.0), base, 0.4)
        self._send(head, sent_pitch, base, 0.4)
        self._sleep(self.settle_s)  # still before the camera checks the point (a small thing blurs out mid-move)

    def say(self, text: str) -> None:
        if self._say:
            self._say(text)

    def _sway(self, offsets) -> None:
        """Pollen's wobbler turns the speech being played into small head offsets; the loop adds them."""
        self.motion.speech = tuple(offsets)

    def gesture(self, name: str) -> None:
        """Body language (robot/motion.py): idle, listening, thinking, searching (holds still), found (an antenna
        wiggle), nod. A nod is a move of its own; the base always stays where it is (goto_target's body_yaw
        defaults to 0, which would swing it back to the middle)."""
        if name == "found":
            self.motion.wiggle(time.monotonic())
        elif name == "nod":
            head, pitch, base = self._sent
            self._send(head, pitch + 8.0, base, 0.25)
            self._send(head, pitch, base, 0.25)
        else:
            self.motion.set_mode(name)

    def emote(self, name: str, sound: bool = True) -> bool:
        """One of Pollen's recorded emotions (pollen-robotics/reachy-mini-emotions-library, Apache-2.0: head, antennas
        and a sound of its own; recorded moves, not a model), then back to exactly where the head was. Only at calm
        moments the app chooses, never while a search or a point needs the head still."""
        try:
            if self._emotions is None:
                from reachy_mini.motion.recorded_move import RecordedMoves

                self._emotions = RecordedMoves(EMOTIONS)
            move = self._emotions.get(name)
        except Exception:  # noqa: BLE001 - no library (offline, first run): no emotion, and nothing else changes
            return False
        with self._moving:  # the body-language loop waits
            self.robot.play_move(move, initial_goto_duration=0.4, sound=sound)
            self._send(*self._sent, 0.5)
        return True

    # --- the speaker and the microphone array (16 kHz) ---

    def play(self, samples, rate: int = 16000) -> None:
        """Play mono float samples through the robot's speaker and wait until they're done."""
        if not getattr(self, "_playing", False):
            self.robot.media.start_playing()
            if self._full_pose is not None:
                self.robot.media.enable_wobbling(self._sway)  # Pollen's speech-driven head motion
            self._playing = True
        self.speaking, before = True, self.motion.mode
        self.motion.set_mode("speaking")
        try:
            self.robot.media.push_audio_sample(samples)
            self._sleep(len(samples) / rate)
        finally:
            self.speaking = False
            self.motion.set_mode("idle" if before in ("speaking", "listening") else before)
            self._quiet_until = time.monotonic() + 0.4  # the room's echo of Andy's own voice

    def listen(self, stop, poll_s: float = 0.02):
        """Yield (mono samples, speech detected, direction of the voice as a yaw) until ``stop`` is set.

        Nothing is yielded while Andy is speaking, so it never hears itself. The direction comes from the microphone
        array: an angle a in the head's frame points at (sin a, cos a), so the voice is 90 - a degrees to the left of
        where the head looks (Pollen's examples/sound_doa.py).
        """
        import numpy as np

        media = self.robot.media
        media.start_recording()
        try:
            while not stop.is_set():
                chunks = []
                # Each pull waits up to 20 ms and 10 ms chunks keep arriving, so take about 100 ms at a time.
                while len(chunks) < 10 and (c := media.get_audio_sample()) is not None:
                    chunks.append(c)
                if chunks and not getattr(self, "speaking", False) and time.monotonic() >= getattr(self, "_quiet_until", 0):
                    audio = np.concatenate(chunks)
                    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
                    doa = media.get_DoA()
                    flag = bool(doa and doa[1])
                    yaw = self.yaw + 90.0 - math.degrees(doa[0]) if flag else None
                    yield mono, flag, yaw
                if not chunks:
                    self._sleep(poll_s)
        finally:
            media.stop_recording()
