"""Muse Glimmer on the computer beside the robot, through llama.cpp's or Ollama's OpenAI-compatible server."""
from .common import Reply
from .openai_chat import chat


class GlimmerModel:
    def __init__(self, model: str = "muse-glimmer-30B", endpoint: str = "http://127.0.0.1:8080/v1", client=None):
        self.model, self.endpoint, self._client = model, endpoint, client

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.endpoint, api_key="local")  # local servers ignore the key
        return self._client

    def chat(self, prompt: str) -> Reply:
        return chat(self.client, self.model, prompt, source="device")
