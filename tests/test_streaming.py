from types import SimpleNamespace

from heyandy_meta.models.openai_chat import sentences, stream
from heyandy_meta.models.common import Reply
from tests.test_app import andy


class Streaming:
    """Plays a streaming chat server: the reply arrives in small pieces, thinking first (never spoken)."""

    def __init__(self, text, think="Let me think about this."):
        self.pieces = [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content=think))])]
        self.pieces += [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text[i:i + 4]))])
                        for i in range(0, len(text), 4)]
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.requests = []

    def _create(self, **kw):
        self.requests.append(kw)
        return iter(self.pieces)


def test_sentences_come_out_as_they_are_written():
    client = Streaming("It's 3.5 degrees out. Wrap up warm! Shall I remind you to take a coat")
    out = list(stream(client, "m", "cold?"))
    assert out == ["It's 3.5 degrees out.", "Wrap up warm!", "Shall I remind you to take a coat"]
    assert client.requests[0]["stream"] is True


def test_sentences_split_a_whole_text_the_same_way():
    assert sentences("Hello there. How are you?") == ["Hello there.", "How are you?"]
    assert sentences("") == []


class StreamingDevice:
    def __init__(self, parts):
        self.parts, self.asked = parts, []

    def chat(self, prompt, history=()):
        return Reply(" ".join(self.parts), "device")

    def stream(self, prompt, history=()):
        self.asked.append(prompt)
        yield from self.parts


def said(body):
    return [e[1] for e in body.log if e[0] == "say"]


def test_the_ai_opening_is_said_before_the_answer_is_made(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    a.device = a.router.device = StreamingDevice(["I'm well, thanks.", "And you?"])
    reply = a.hear("how are you")
    assert reply == "I'm Andy, an AI robot. I'm well, thanks. And you?"
    assert said(body) == ["I'm Andy, an AI robot.", "I'm well, thanks.", "And you?"]  # each said once, in order


def test_a_promise_in_the_middle_stops_the_answer(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    a.device = a.router.device = StreamingDevice(["Sure.", "I'll remind you at five.", "Anything else?"])
    reply = a.hear("can you help me later on")
    assert said(body)[-2:] == ["Sure.", reply.split("Sure. ")[1]] and "Say it to me directly" in reply
    assert "Anything else?" not in reply
