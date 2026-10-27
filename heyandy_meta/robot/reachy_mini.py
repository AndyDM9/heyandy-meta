"""The Reachy Mini adapter: the only module that imports Pollen's SDK.

A direction is split between the head (up to ``head_yaw`` either way) and a turn of the base, sent as one smooth
move. Moves are slow enough to be gentle (about 70 degrees a second at most), and every direction is clamped to the
body's reach first. The split and the base turn are untested on the robot until Day 2.
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


class ReachyBody:
    def __init__(self, robot=None, reach: Reach = Reach(), head_yaw: float = 55.0, max_deg_s: float = 70.0,
                 settle_s: float = 0.3, pose=None, say=None, sleep=time.sleep):
        if robot is None:
            from reachy_mini import ReachyMini

            robot = ReachyMini(automatic_body_yaw=False)
        if pose is None:
            from reachy_mini.utils import create_head_pose

            pose = lambda yaw, pitch: create_head_pose(yaw=yaw, pitch=pitch, degrees=True)  # noqa: E731
        self.robot, self.reach, self.head_yaw = robot, reach, head_yaw
        self.max_deg_s, self.settle_s = max_deg_s, settle_s
        self._pose, self._say, self._sleep = pose, say, sleep
        self.yaw = self.pitch = 0.0

    def split(self, yaw: float) -> tuple[float, float]:
        """(head yaw, base yaw) for a direction: the head turns first, the base makes up the rest."""
        head = max(-self.head_yaw, min(self.head_yaw, yaw))
        return head, yaw - head

    def look(self, yaw: float, pitch: float) -> None:
        yaw, pitch = self.reach.clamp(yaw, pitch)
        travel = max(abs(yaw - self.yaw), abs(pitch - self.pitch))
        head, base = self.split(yaw)
        self.robot.goto_target(head=self._pose(head, pitch), body_yaw=math.radians(base),
                               duration=max(0.6, travel / self.max_deg_s))
        self.yaw, self.pitch = yaw, pitch
        self._sleep(self.settle_s)  # let the camera stop moving before a frame is read

    def capture(self) -> Frame:
        data = self.robot.media.get_frame_jpeg()
        if not data:
            raise RuntimeError("the camera returned no frame")
        w, h = jpeg_size(data)
        return Frame(data, w, h, self.yaw, self.pitch)

    def point(self, yaw: float, pitch: float) -> None:
        """Point with the head: face the thing, dip once towards it, and hold."""
        self.look(yaw, pitch)
        yaw, pitch = self.reach.clamp(yaw, pitch)
        head, base = self.split(yaw)
        dip = min(pitch + 6.0, self.reach.pitch_down)
        self.robot.goto_target(head=self._pose(head, dip), body_yaw=math.radians(base), duration=0.4)
        self.robot.goto_target(head=self._pose(head, pitch), body_yaw=math.radians(base), duration=0.4)

    def say(self, text: str) -> None:
        if self._say:
            self._say(text)
