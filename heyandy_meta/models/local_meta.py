"""Muse Glimmer on the computer beside the robot, through llama.cpp's or Ollama's OpenAI-compatible server."""
from .common import Reply, on_this_computer
from .openai_chat import chat, stream


class GlimmerModel:
    def __init__(self, model: str = "muse-glimmer-30B", endpoint: str = "http://127.0.0.1:8080/v1", client=None):
        if not on_this_computer(endpoint):  # the person's words, and what the camera saw, stay on this computer
            raise ValueError(f"Glimmer runs on this computer or the home network, not at {endpoint}")
        self.model, self.endpoint, self._client = model, endpoint, client

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.endpoint, api_key="local")  # local servers ignore the key
        return self._client

    def chat(self, prompt: str, history=()) -> Reply:
        return chat(self.client, self.model, prompt, source="device", history=history)

    def stream(self, prompt: str, history=()):
        """Sentence by sentence, as Glimmer writes them."""
        return stream(self.client, self.model, prompt, history)
