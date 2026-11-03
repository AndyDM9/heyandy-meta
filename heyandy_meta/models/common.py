"""What every model here returns."""
import ipaddress
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


def is_local(url: str) -> bool:
    """This computer or the home network: inside the home (what the web browser never opens, and where the TV may be
    shown). Andy's models are held to on_this_computer()."""
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def on_this_computer(url: str) -> bool:
    """This computer only: where the camera's pictures, the microphone's sound and the person's words may go to a model
    (the system card: "on the computer beside the robot"). Every model server of Andy's listens on 127.0.0.1."""
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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


# What SAM 3.1 is asked for a thing, where the plain word finds the wrong thing: asked for "keys", it outlines every
# key of a keyboard (28 of 28 masks on the keyboard, on the Lite, 2026-10-31); "bunch of keys" found only the keys
# (0.91 and 0.89, from two views). The masks come back under the word Andy used.
SAM_ASKS = {"keys": "bunch of keys", "key": "set of keys", "car keys": "bunch of keys", "house keys": "bunch of keys"}


def sam_asks(query: str) -> str:
    return SAM_ASKS.get(query.strip().lower(), query)
