"""What every model here returns."""
import ipaddress
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


def is_local(url: str) -> bool:
    """This computer or the home network: where pictures from a home may go."""
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


@dataclass
class Reply:
    text: str
    source: str  # "device" (Glimmer beside the robot) or "cloud" (the Meta Model API)
    latency_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class Chat(Protocol):
    def chat(self, prompt: str, history=()) -> Reply: ...


@dataclass
class Mask:
    """One object found in a frame, in the frame's pixels."""

    label: str
    box: tuple[int, int, int, int]  # left, top, right, bottom; right and bottom exclusive
    score: float | None  # SAM's 0-1 confidence; None when not returned (not zero)
    center: tuple[float, float] = (0.0, 0.0)  # the mask's centre of mass
    area: int = 0  # mask pixels
    outline: str = ""  # SVG path in the mask's own pixels; place it with translate(box[0], box[1]) scale(*outline_scale)
    outline_scale: tuple[float, float] = (1.0, 1.0)
