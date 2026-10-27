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
import time

from .body import Frame, Reach


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


class ReachyBody:
    def __init__(self, robot=None, reach: Reach = Reach(), head_yaw: float = 30.0, max_deg_s: float = 70.0,
                 settle_s: float = 0.3, tolerance: float = 1.5, pose=None, say=None, sleep=time.sleep):
        if robot is None:
            from reachy_mini import ReachyMini

            # Never media_backend="no_media": it makes the daemon release the camera and audio for everyone.
            robot = ReachyMini(automatic_body_yaw=False, connection_mode="localhost_only").__enter__()
        if pose is None:
            from reachy_mini.utils import create_head_pose

            pose = lambda yaw, pitch: create_head_pose(yaw=yaw, pitch=pitch, degrees=True)  # noqa: E731
        self.robot, self.reach, self.head_yaw, self.tolerance = robot, reach, head_yaw, tolerance
        self.max_deg_s, self.settle_s = max_deg_s, settle_s
        self._pose, self._say, self._sleep = pose, say, sleep
        self.yaw = self.pitch = 0.0  # where the head is looking, measured when the robot can tell us
        self._sent = (0.0, 0.0, 0.0)  # the last head yaw, pitch and base yaw sent

    def split(self, yaw: float) -> tuple[float, float]:
        """(head yaw, base yaw) for a direction: the head turns first, the base makes up the rest."""
        head = max(-self.head_yaw, min(self.head_yaw, yaw))
        return head, yaw - head

    def measured(self) -> tuple[float, float] | None:
        """Where the head really looks: its yaw on the body plus the base's yaw, and its pitch."""
        if not hasattr(self.robot, "get_current_head_pose"):
            return None
        head_yaw, pitch = _yaw_pitch(self.robot.get_current_head_pose())
        base = math.degrees(self.robot.get_current_joint_positions()[0][0])
        return head_yaw + base, pitch

    def _send(self, head: float, pitch: float, base: float, duration: float) -> None:
        self.robot.goto_target(head=self._pose(head, pitch), body_yaw=math.radians(base), duration=duration)
        self._sent = (head, pitch, base)

    def look(self, yaw: float, pitch: float, precise: bool = True) -> None:
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

    def point(self, yaw: float, pitch: float) -> None:
        """Point with the head: face the thing, dip once towards it, and hold."""
        self.look(yaw, pitch)
        head, sent_pitch, base = self._sent
        self._send(head, min(sent_pitch + 6.0, self.reach.pitch_down + 10.0), base, 0.4)
        self._send(head, sent_pitch, base, 0.4)

    def say(self, text: str) -> None:
        if self._say:
            self._say(text)

    # --- the speaker and the microphone array (16 kHz) ---

    def play(self, samples, rate: int = 16000) -> None:
        """Play mono float samples through the robot's speaker and wait until they're done."""
        if not getattr(self, "_playing", False):
            self.robot.media.start_playing()
            self._playing = True
        self.speaking = True
        try:
            self.robot.media.push_audio_sample(samples)
            self._sleep(len(samples) / rate)
        finally:
            self.speaking = False
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
