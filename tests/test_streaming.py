from types import SimpleNamespace

import pytest

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


# --- each sentence's voice made as it arrives (heyandy_meta/app.py _ahead, voice/speaker.py prepare) ---

class Ahead:
    """A body that makes sentences ahead, as the robot's does, and logs when each was prepared, said, or dropped."""

    def __init__(self, body):
        self.body, self.events = body, []

    def __getattr__(self, name):
        return getattr(self.body, name)

    def prepare(self, text):
        self.events.append(("prepare", text))

    def unprepare(self):
        self.events.append(("unprepare", None))

    def say(self, text):
        self.events.append(("say", text))
        self.body.say(text)


def ahead_andy(tmp_path, parts):
    a, body, clock = andy(tmp_path=tmp_path)
    a.hear("hello")  # the first turn's "I'm Andy, an AI robot." is out of the way
    a.body = Ahead(body)
    a.device = a.router.device = StreamingDevice(parts)
    return a, body


def test_each_sentence_is_made_ahead_and_still_said_once_in_order(tmp_path):
    a, body = ahead_andy(tmp_path, ["I'm well, thanks.", "The sun is out.", "And you?"])
    reply = a.hear("how are you")
    assert reply == "I'm well, thanks. The sun is out. And you?"
    assert said(body)[-3:] == ["I'm well, thanks.", "The sun is out.", "And you?"]
    for sentence in ["I'm well, thanks.", "The sun is out.", "And you?"]:  # made ahead before it was said
        assert a.body.events.index(("prepare", sentence)) < a.body.events.index(("say", sentence))


def test_an_answer_the_checks_stop_drops_what_was_made_ahead_before_andys_own_words(tmp_path):
    from heyandy_meta.companion.safety import HEALTH_REPLY
    from tests.test_no_advice import Guard

    a, body = ahead_andy(tmp_path, ["Good question.", "Drink eight glasses of water a day.", "Cheers!"])
    a.guard = Guard(advice=["eight glasses"])
    reply = a.hear("how much water should I drink")
    assert said(body)[-2:] == ["Good question.", HEALTH_REPLY] and "Cheers" not in reply
    events = a.body.events
    assert events.index(("unprepare", None)) < events.index(("say", HEALTH_REPLY))  # nothing made ahead in its way


def test_the_models_error_still_reaches_the_turn(tmp_path):
    from openai import APIError

    class Broken(StreamingDevice):
        def stream(self, prompt, history=()):
            yield "Let me see."
            raise APIError("gone", request=None, body=None)

    a, body = ahead_andy(tmp_path, [])
    a.device = a.router.device = Broken([])
    reply = a.hear("tell me something")
    assert reply.startswith("Let me see.") and "trouble thinking" in reply


def test_in_another_language_nothing_is_made_ahead(tmp_path):
    a, body = ahead_andy(tmp_path, ["Estoy bien.", "¿Y usted?"])
    a.language = "es"
    a.hear("cómo estás")
    assert not [e for e in a.body.events if e[0] == "prepare"]  # translated when said: made then


def test_the_speaker_uses_what_was_made_ahead_and_makes_each_sentence_once():
    from heyandy_meta.voice.speaker import Speaker

    made, played = [], []

    class Voice:
        voice, speed, loudness = "eng", 1.0, 0.0

        def speak(self, text, rate=16000):
            made.append(text)
            return text

    s = Speaker(Voice(), lambda audio, rate: played.append(audio))
    s.prepare("I'm well, thanks. The sun is out today, isn't it lovely.")
    s.prepare("I'm well, thanks.")  # asked again: made once
    s("I'm well, thanks.")
    s("The sun is out today, isn't it lovely.")
    assert played == ["I'm well, thanks.", "The sun is out today, isn't it lovely."]
    assert made == ["I'm well, thanks.", "The sun is out today, isn't it lovely."]


def test_dropping_what_was_made_ahead_stops_what_hasnt_started():
    import threading

    from heyandy_meta.voice.speaker import Speaker

    gate, made = threading.Event(), []

    class Voice:
        def speak(self, text, rate=16000):
            gate.wait(2)
            made.append(text)
            return text

    s = Speaker(Voice(), lambda audio, rate: None)
    s.prepare("One sentence that is long enough. Two sentence that is long enough. Three sentence that is long enough.")
    s.unprepare()
    gate.set()
    s("Andy's own words, said now and at once.")
    assert made[-1] == "Andy's own words, said now and at once." and len(made) <= 2  # at most the one already started


def test_the_speech_gaps_scorecard_keeps_the_turns_order_and_measures_silence():
    from evals import speech_gaps

    clock = [0.0]
    events, made = [], []

    class Pretend:
        def prepare(self, text):
            made.append(text)

        def __call__(self, text):
            ready = text in made
            clock[0] += 0.0 if ready else 0.5  # made when said: half a second of silence first
            events.append(("start", clock[0]))
            clock[0] += 2.0
            events.append(("end", clock[0]))

    sleep = lambda s: clock.__setitem__(0, clock[0] + s)  # noqa: E731
    before = speech_gaps.summary(speech_gaps.run(Pretend(), events, ahead=False, sleep=sleep, clock=lambda: clock[0]))
    after = speech_gaps.summary(speech_gaps.run(Pretend(), events, ahead=True, sleep=sleep, clock=lambda: clock[0]))
    assert before["silence between sentences, median s"] == pytest.approx(0.55)  # the check and the making
    assert after["silence between sentences, median s"] == pytest.approx(0.05)  # the check only
    assert after["first sound, median s"] == pytest.approx(0.95) and before["first sound, median s"] == pytest.approx(1.45)
