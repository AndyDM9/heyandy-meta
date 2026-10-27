"""Stand-ins for the OpenAI-compatible client, so no test makes a network call or spends credits."""
from types import SimpleNamespace


class FakeClient:
    def __init__(self, reply: str = "ok", sam_output: str = ""):
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.responses = SimpleNamespace(stream=self._stream)
        self._reply, self._sam_output = reply, sam_output

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._reply))],
                               usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        final = SimpleNamespace(output_text=self._sam_output)
        return _Stream(final)


class _Stream:
    def __init__(self, final):
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_response(self):
        return self._final
