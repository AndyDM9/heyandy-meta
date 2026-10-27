"""Muse Spark through the Meta Model API, for hard questions. Standard tier only: Meta may train on Contributor-tier inputs."""
import os

from ..budget import Budget, chat_cost
from .common import Reply
from .openai_chat import chat

BASE_URL = "https://api.meta.ai/v1"


class MuseSparkModel:
    name = "muse-spark"

    def __init__(self, model: str = "muse-spark-1.3", client=None, api_key_env: str = "MODEL_API_KEY",
                 base_url: str = BASE_URL, budget: Budget | None = None, max_tokens: int = 1500,
                 reasoning_effort: str = "minimal"):
        if "contributor" in model:
            raise ValueError("Contributor-tier models are not allowed: Meta may train on their inputs")
        self.model, self._client = model, client
        self.budget, self.max_tokens, self.reasoning_effort = budget or Budget(), max_tokens, reasoning_effort
        self._api_key_env, self._base_url = api_key_env, base_url

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            key = os.environ.get(self._api_key_env)  # never hard-code keys
            if not key:
                raise RuntimeError(f"{self._api_key_env} is not set")
            self._client = OpenAI(base_url=self._base_url, api_key=key)
        return self._client

    def chat(self, prompt: str, history=()) -> Reply:
        words = len(prompt) + sum(len(a) + len(b) for a, b in history)
        worst = chat_cost(self.model, words // 2 + 200, self.max_tokens)  # generous token guess, before the call
        self.budget.check(worst)
        reply = chat(self.client, self.model, prompt, source="cloud", max_tokens=self.max_tokens, history=history,
                     reasoning_effort=self.reasoning_effort)  # measured: 116 thinking tokens and 2.7 s, against 550
        self.budget.record(self.model, chat_cost(self.model, reply.tokens_in, reply.tokens_out) if reply.tokens_in else worst)
        return reply
