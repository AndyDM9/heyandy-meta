"""What the rest of the code may ask of a robot body. Vendor SDKs are imported only by an adapter behind this.

The finder asks the body to look in a direction or point; it never sends motor values. The adapter decides how:
past the head's own reach it turns the base, and it refuses directions outside its limits.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Frame:
    image: bytes  # JPEG
    width: int
    height: int
    yaw: float  # where the head was looking when it was taken
    pitch: float


@dataclass(frozen=True)
class Reach:
    yaw: float = 160.0  # head and base together; the head alone turns about ±60
    pitch_up: float = -30.0  # pitch is positive down
    pitch_down: float = 35.0

    def clamp(self, yaw: float, pitch: float) -> tuple[float, float]:
        return max(-self.yaw, min(self.yaw, yaw)), max(self.pitch_up, min(self.pitch_down, pitch))

    def allows(self, yaw: float, pitch: float) -> bool:
        return (yaw, pitch) == self.clamp(yaw, pitch)


class Body(Protocol):
    reach: Reach

    def look(self, yaw: float, pitch: float, precise: bool = True) -> None:
        """Turn to a direction. precise=False skips fine correction: fine when the frame says where it was taken."""
    def capture(self) -> Frame: ...
    def point(self, yaw: float, pitch: float) -> None: ...
    def say(self, text: str) -> None: ...
