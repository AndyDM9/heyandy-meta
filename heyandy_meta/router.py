"""Who answers a turn: Glimmer on the device, or Muse Spark in the cloud.

The device answers by default. A turn goes to the cloud only when it looks like it needs more thought and the
robot is online. If the cloud is refused (no budget, or paid calls switched off), the device answers instead of
the robot going quiet.
"""
from dataclasses import dataclass

from .budget import BudgetExceeded
from .models.common import Chat, Reply

THINKING_WORDS = ("explain", "why", "compare", "research", "how does", "what does")


@dataclass(frozen=True)
class Decision:
    where: str  # "device" or "cloud"
    reason: str  # shown on the TV under the answer


def decide(prompt: str, online: bool = True, long_chars: int = 400) -> Decision:
    if not online:
        return Decision("device", "offline")
    p = prompt.lower()
    if len(prompt) > long_chars:
        return Decision("cloud", "long question")
    word = next((w for w in THINKING_WORDS if w in p), None)
    if word:
        return Decision("cloud", f"needs more thought ({word!r})")
    return Decision("device", "everyday turn")


class Router:
    def __init__(self, device: Chat, cloud: Chat):
        self.device, self.cloud = device, cloud
        self.last: Decision | None = None

    def answer(self, prompt: str, online: bool = True) -> Reply:
        self.last = decide(prompt, online)
        if self.last.where == "cloud":
            try:
                return self.cloud.chat(prompt)
            except BudgetExceeded as refused:
                self.last = Decision("device", f"cloud refused: {refused}")
        return self.device.chat(prompt)
