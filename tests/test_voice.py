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
    """...but only with some sound behind it: alone (motor hum, a TV) it could hold a stretch open for ever."""
    ep = Endpointer()
    for c in chunks(1.0, 0):
        ep.feed(c)
    out = [u for c in chunks(0.5, 0.021, 1) if (u := ep.feed(c, True)) is not None]  # soft speech: the detector decides
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

    def turn_to_person(self, yaw, pitch=None):
        self.body.look(yaw, 5.0)


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


@pytest.mark.parametrize("heard", ["andy where are my keys", "and they where are my keys", "earndy, where are my keys",
                                   "Hey Andy! Where are my keys?", "ok andi where are my keys"])
def test_the_name_as_speech_to_text_writes_it(heard):
    a = Andy()
    VoiceLoop(a).heard(heard)
    assert [h.lower().strip(" ?") for h in a.heard] == ["where are my keys"]


def test_and_counts_as_andy_only_before_a_clear_request():
    a = Andy()
    loop = VoiceLoop(a)
    assert loop.heard("and can you find the watch") == "ok" and a.heard == ["can you find the watch"]
    a2 = Andy()
    assert VoiceLoop(a2).heard("and you good morning") is None and a2.heard == []


def test_looping_speech_to_text_is_dropped():
    a = Andy()
    loop = VoiceLoop(a)
    loop.awake_until = float("inf")
    assert loop.heard("the state of " * 12) is None and a.heard == []
    assert loop.heard("and the remote, is it on the sofa or by the window or under the cushion") == "ok"


def test_the_name_later_in_a_long_stretch_still_counts():
    a = Andy()
    assert VoiceLoop(a).heard("so we went there yesterday and it was fine andy how are you") == "ok"
    assert a.heard == ["how are you"]


def test_a_stretch_is_cut_at_eight_seconds():
    ep = Endpointer()
    for c in chunks(1.0, 0):
        ep.feed(c)
    out = [u for c in chunks(12.0, 0.3, 1) if (u := ep.feed(c)) is not None]
    assert out and len(out[0]) / RATE == pytest.approx(8.0, abs=0.4)


def test_stop_reaches_a_follow_at_once():
    a = Andy()
    a.following, stopped = True, []
    a.stop_following = lambda: stopped.append(True)
    assert VoiceLoop(a).heard("stop") == "Stopped." and stopped == [True] and a.heard == []


def test_stop_is_heard_while_a_turn_is_running():
    """Turns run on their own thread: the microphone keeps listening, so "done" reaches the cup game mid-shuffle."""
    import threading

    stop, stopped, said = threading.Event(), threading.Event(), iter(["andy let's play the cup game", "okay done"])

    class Playing(Andy):
        following = playing = False

        def hear(self, text):
            self.following = self.playing = True
            ok = stopped.wait(3.0)
            self.following = self.playing = False
            return "stopped" if ok else "never heard"

        def stop_following(self):
            stopped.set()

    class Ears:
        active, rate, end_silence_s, floor = False, RATE, 0.5, 0.0

        def feed(self, samples, flag):
            return samples

    def mic(stop):
        yield np.zeros(RATE, np.float32), True, None
        while not a.following:
            stop.wait(0.01)
        yield np.zeros(RATE, np.float32), True, None
        stop.wait(3.0)

    a, replies = Playing(), []
    loop = VoiceLoop(a, on_heard=lambda text, reply: replies.append(reply))
    voice = SimpleNamespace(transcribe=lambda audio: next(said))
    t = threading.Thread(target=loop.run, args=(mic, voice, Ears(), stop), daemon=True)
    t.start()
    assert stopped.wait(3.0)
    for _ in range(100):
        if "stopped" in replies:
            break
        stop.wait(0.02)
    stop.set()
    assert replies == ["Stopped.", "stopped"] and not loop.busy


def test_crisis_words_during_a_turn_stop_it_and_are_answered_next():
    import threading

    stop, said = threading.Event(), iter(["andy follow the mug", "andy stop, I want to kill myself"])
    heard, stopped = [], threading.Event()

    class Busy(Andy):
        following = False

        def hear(self, text):
            heard.append(text)
            if len(heard) == 1:
                self.following = True
                stopped.wait(3.0)
                self.following = False
                return "Okay, I've stopped."
            return "crisis reply"

        def stop_following(self):
            stopped.set()

    class Ears:
        active, rate, end_silence_s, floor = False, RATE, 0.5, 0.0

        def feed(self, samples, flag):
            return samples

    def mic(stop):
        yield np.zeros(RATE, np.float32), True, None
        while not a.following:
            stop.wait(0.01)
        yield np.zeros(RATE, np.float32), True, None
        stop.wait(3.0)

    a = Busy()
    loop = VoiceLoop(a)
    t = threading.Thread(target=loop.run, args=(mic, SimpleNamespace(transcribe=lambda audio: next(said)), Ears(), stop),
                         daemon=True)
    t.start()
    for _ in range(200):
        if len(heard) == 2:
            break
        stop.wait(0.02)
    stop.set()
    assert stopped.is_set() and heard[1] == "andy stop, I want to kill myself"  # the whole of it, not dropped


def test_the_whole_utterance_is_checked():
    a = Andy()
    VoiceLoop(a).heard("I want to kill myself. Andy, what time is it")
    assert a.heard == ["I want to kill myself. Andy, what time is it"]
