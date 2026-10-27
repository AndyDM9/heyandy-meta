import threading
from types import SimpleNamespace

import numpy as np
import pytest

from heyandy_meta.models.sam_local import NotLocal
from heyandy_meta.voice.listen import Endpointer
from heyandy_meta.voice.local import LocalVoice
from heyandy_meta.voice.loop import VoiceLoop
from heyandy_meta.voice.speaker import Speaker

RATE, CHUNK = 16000, 160  # 10 ms chunks, as the robot's microphone delivers them


def chunks(seconds, level, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    tone = level * np.sin(2 * np.pi * 220 * np.arange(n) / RATE) if level > 0.02 else 0
    audio = (rng.normal(0, 0.01, n) + tone).astype(np.float32)
    return [audio[i:i + CHUNK] for i in range(0, n, CHUNK)]


def run(ep, parts):
    return [u for c in parts if (u := ep.feed(c)) is not None]


def test_one_utterance_from_quiet_speech_quiet():
    ep = Endpointer()
    out = run(ep, chunks(1.0, 0) + chunks(1.2, 0.3, 1) + chunks(1.0, 0, 2))
    assert len(out) == 1
    assert 1.2 + 0.6 <= len(out[0]) / RATE <= 1.2 + 0.3 + 0.8  # the speech, a little before, the silence after


def test_a_click_is_not_speech():
    ep = Endpointer()
    assert run(ep, chunks(1.0, 0) + chunks(0.05, 0.5, 1) + chunks(1.0, 0, 2)) == []


def test_the_microphones_own_detector_counts_too():
    ep = Endpointer()
    for c in chunks(1.0, 0):
        ep.feed(c)
    out = [u for c in chunks(0.5, 0, 1) if (u := ep.feed(c, True)) is not None]
    out += [u for c in chunks(1.0, 0, 2) if (u := ep.feed(c, False)) is not None]
    assert len(out) == 1


class Andy:
    def __init__(self):
        self.heard, self.said = [], []
        self.body = SimpleNamespace(looks=[], look=lambda y, p, precise=True: self.body.looks.append((y, p)))

    def hear(self, text):
        self.heard.append(text)
        return "ok"

    def say(self, text):
        self.said.append(text)


def test_only_speech_for_andy_is_answered_and_follow_ups_need_no_name():
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    assert loop.heard("what a lovely day") is None
    assert loop.heard("hey andy where are my glasses", voice_yaw=40.0) == "ok"
    assert a.heard == ["where are my glasses"] and a.body.looks == [(40.0, 5.0)]
    t[0] = 10
    assert loop.heard("and my keys") == "ok"
    t[0] = 40
    assert loop.heard("talking to someone else") is None


def test_just_the_name_gets_a_yes():
    a = Andy()
    assert VoiceLoop(a).heard("Andy.") == "Yes?" and a.said == ["Yes?"] and a.heard == []


def test_the_speaker_says_one_sentence_at_a_time():
    said, played = [], []
    voice = SimpleNamespace(speak=lambda s, rate: said.append(s) or np.zeros(8, np.float32))
    Speaker(voice, lambda samples, rate: played.append(rate))("I see your glasses. They're to my right! Anything else?")
    assert said == ["I see your glasses.", "They're to my right!", "Anything else?"] and played == [16000] * 3


def test_speech_stays_on_this_computer():
    with pytest.raises(NotLocal):
        LocalVoice("https://api.meta.ai/v1")
