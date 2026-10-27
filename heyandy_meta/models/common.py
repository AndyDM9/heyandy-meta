"""What every model here returns."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Reply:
    text: str
    source: str  # "device" (Glimmer beside the robot) or "cloud" (the Meta Model API)
    latency_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class Chat(Protocol):
    def chat(self, prompt: str) -> Reply: ...


@dataclass
class Mask:
    """One object found in a frame, in the frame's pixels."""

    label: str
    box: tuple[int, int, int, int]  # left, top, right, bottom; right and bottom exclusive
    score: float | None  # SAM's 0-1 confidence; None when not returned (not zero)
    center: tuple[float, float] = (0.0, 0.0)  # the mask's centre of mass
    area: int = 0  # mask pixels
