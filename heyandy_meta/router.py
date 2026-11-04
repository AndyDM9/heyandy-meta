"""Who answers a turn: Glimmer on the device, or Muse Spark in the cloud.

The device answers by default. A turn goes to the cloud only when it looks like it needs more thought and the
robot is online. If the cloud is refused (no budget, or paid calls switched off) or keeps failing, the device
answers instead of the robot going quiet. And if the device isn't answering (a laptop with only a Model API key, or
Glimmer's service down), an everyday turn goes to the cloud, its words on the turn's receipt.
"""
from collections.abc import Callable
from dataclasses import dataclass

from openai import APIError

from .budget import BudgetExceeded
from .models.common import Chat, Reply
from .models.openai_chat import sentences
from .models.retry import CloudUnavailable

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
    def __init__(self, device: Chat, cloud: Chat, on_cloud: Callable[[str], None] | None = None):
        """on_cloud: puts a turn's words on its receipt. Without it (no Model API key), the device never hands over."""
        self.device, self.cloud, self.on_cloud = device, cloud, on_cloud
        self.last: Decision | None = None

    def _cloud_instead(self, prompt: str, online: bool, history, down: APIError) -> Reply:
        """The device didn't answer an everyday turn: the cloud does, or the device's own error stands."""
        if not online or self.on_cloud is None or self.last.reason != "everyday turn":
            raise down
        try:
            reply = self.cloud.chat(prompt, history)
        except BudgetExceeded:
            raise down from None  # refused before anything was sent
        except (CloudUnavailable, APIError):
            self.on_cloud(prompt)  # the words may have gone even though no answer came
            raise down from None
        self.on_cloud(prompt)
        self.last = Decision("cloud", "Muse Glimmer isn't answering on this computer")
        return reply

    def answer(self, prompt: str, online: bool = True, history=()) -> Reply:
        self.last = decide(prompt, online)
        if self.last.where == "cloud":
            try:
                return self.cloud.chat(prompt, history)
            except BudgetExceeded as refused:
                self.last = Decision("device", f"cloud refused: {refused}")
            except CloudUnavailable as down:
                self.last = Decision("device", f"cloud unavailable: {down}")
        try:
            return self.device.chat(prompt, history)
        except APIError as down:
            return self._cloud_instead(prompt, online, history, down)

    def stream(self, prompt: str, online: bool = True, history=()):
        """Like answer(), sentence by sentence: the device streams as it writes; the cloud's answer comes whole.
        Afterwards, self.last says who answered and why."""
        self.last = decide(prompt, online)
        if self.last.where == "cloud":
            try:
                text = self.cloud.chat(prompt, history).text
            except BudgetExceeded as refused:
                self.last = Decision("device", f"cloud refused: {refused}")
            except CloudUnavailable as down:
                self.last = Decision("device", f"cloud unavailable: {down}")
            else:
                yield from sentences(text)
                return
        live = getattr(self.device, "stream", None)
        said = False
        try:
            for sentence in live(prompt, history) if live else sentences(self.device.chat(prompt, history).text):
                said = True
                yield sentence
        except APIError as down:
            if said:
                raise  # part of an answer is out: it isn't started again by someone else
            yield from sentences(self._cloud_instead(prompt, online, history, down).text)
