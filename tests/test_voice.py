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


def test_a_near_silent_sound_without_the_name_is_not_a_follow_up():
    """November 4: the microphone array gone faint, speech-to-text wrote words out of near-silence, and in the window
    after a reply Andy answered them, six in a row, to nobody. A sound quieter than any voice isn't speech for Andy;
    called by name, it's answered whatever the level."""
    from heyandy_meta.voice.loop import _loudness

    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    assert loop.heard("hey andy where are my glasses", level=0.06) == "ok"
    t[0] = 5
    assert loop.heard("the state of the room is the state", level=0.004) is None  # words from near-silence: let go
    assert loop.heard("and my keys", level=0.05) == "ok"  # a voice: a follow-up, as before
    assert a.heard == ["where are my glasses", "and my keys"]
    t[0] = 10
    assert loop.heard("hey andy what time is it", level=0.004) == "ok"
    assert _loudness([]) is None and abs(_loudness([0.1, -0.1, 0.1, -0.1]) - 0.1) < 1e-6


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
    loop.awake_until, loop.follow_ups_left = float("inf"), loop.follow_ups  # just answered
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


def test_soon_speech_carries_on_and_what_is_said_next_waits_its_turn():
    """"Let me look." while the head starts turning; the answer only after it."""
    import threading
    import time

    gate, played = threading.Event(), []

    class Voice:
        def speak(self, text, rate=16000):
            return text

    def play(audio, rate):
        if audio == "Let me look.":
            gate.wait(2)  # still playing
        played.append(audio)

    s = Speaker(Voice(), play)
    start = time.monotonic()
    s.soon("Let me look.")
    assert time.monotonic() - start < 0.5 and played == []  # it carried on at once
    threading.Timer(0.2, gate.set).start()
    s("There it is! I see your keys.")
    assert played == ["Let me look.", "There it is!", "I see your keys."]  # in order, never over each other


def test_the_next_sentence_is_made_while_one_plays():
    import time

    made = []

    class Voice:
        def speak(self, text, rate=16000):
            made.append((text, time.monotonic()))
            time.sleep(0.1)
            return text

    plays = []
    Speaker(Voice(), lambda audio, rate: (plays.append((audio, time.monotonic())), time.sleep(0.3)))("One. Two. Three.")
    assert [p[0] for p in plays] == ["One.", "Two.", "Three."]
    assert made[1][1] < plays[0][1] + 0.3  # "Two." was being made while "One." played


def test_short_phrases_are_made_once_per_voice_setting():
    made = []

    class Voice:
        voice, speed, loudness = "eng", 1.0, 0.0

        def speak(self, text, rate=16000):
            made.append(text)
            return text

    v = Voice()
    s = Speaker(v, lambda audio, rate: None)
    s("There it is! I see your keys, a little to my right.")
    s("There it is! I see your glasses, straight ahead.")
    assert made.count("There it is!") == 1 and len(made) == 3  # the long sentences are made each time
    v.speed = 0.85  # "speak more slowly": made again, at the new speed
    s("There it is!")
    assert made.count("There it is!") == 2


def test_soon_speech_never_waits_even_while_something_is_being_said():
    """The first turn's "I'm Andy, an AI robot." played, and "Let me look." waited for it: the search started 2.4 s late
    on the robot. Now both are queued at once, said in order, and the answer after them."""
    import threading
    import time

    gate, played = threading.Event(), []

    class Voice:
        def speak(self, text, rate=16000):
            return text

    def play(audio, rate):
        if audio == "I'm Andy, an AI robot.":
            gate.wait(2)  # still playing
        played.append(audio)

    s = Speaker(Voice(), play)
    start = time.monotonic()
    s.soon("I'm Andy, an AI robot.")
    s.soon("Let me look.")
    assert time.monotonic() - start < 0.3  # neither waited: the search starts at once
    threading.Timer(0.2, gate.set).start()
    s("There it is!")
    assert played == ["I'm Andy, an AI robot.", "Let me look.", "There it is!"]


class Chatty(Andy):
    """Andy whose replies may ask something back, as Muse Glimmer's often do."""

    def __init__(self, reply="ok"):
        super().__init__()
        self.reply = reply

    def hear(self, text):
        self.heard.append(text)
        return self.reply


def test_follow_ups_without_the_name_stop_after_six_in_a_row():
    """November 2: each reply opened the window again, and a meeting near the robot kept it answering for 20 minutes."""
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    assert loop.heard("hey andy how are you") == "ok"
    for i in range(loop.follow_ups):
        t[0] += 10
        assert loop.heard(f"tell me more {i}") == "ok"
    t[0] += 10
    assert loop.follow_ups == 6 and loop.heard("and what about the budget") is None and len(a.heard) == 7
    assert loop.heard("andy what time is it") == "ok"  # the name again: a new conversation, its follow-ups again
    t[0] += 10
    assert loop.heard("and the date") == "ok"


def test_in_a_room_already_talking_andy_answers_its_name_and_takes_nothing_after():
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    for i in range(5):  # a meeting: people talking, none of it to Andy
        t[0] += 6
        assert loop.heard(f"we should move the launch to friday {i}") is None
    assert loop.talking_room()
    assert loop.heard("andy can you check that") == "ok"  # a colleague called Andy, or Andy itself: answered once
    t[0] += 8
    assert loop.heard("yes I agree with that plan") is None  # and the meeting goes on without it
    assert not loop.listening() and len(a.heard) == 1


def test_a_room_that_went_quiet_gets_its_follow_ups_back():
    t = [0.0]
    loop = VoiceLoop(Andy(), follow_up_s=20, clock=lambda: t[0])
    for i in range(5):
        t[0] += 6
        loop.heard(f"people talking {i}")
    t[0] += 120  # past the room's 90 s
    assert not loop.talking_room()
    assert loop.heard("hey andy where are my glasses") == "ok"
    t[0] += 10
    assert loop.heard("and my keys") == "ok"


def test_when_andy_asks_something_in_a_talking_room_one_answer_counts_and_no_chain():
    t = [0.0]
    a = Chatty("Which one do you mean?")
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    for i in range(5):
        t[0] += 6
        loop.heard(f"people talking {i}")
    assert loop.heard("andy put that right") == "Which one do you mean?"
    t[0] += 8
    assert loop.heard("the blue one") == "Which one do you mean?"  # its answer, without the name
    t[0] += 8
    assert loop.heard("I think the quarter went well") is None  # a question back again doesn't open another


def test_just_the_name_in_a_talking_room_still_gets_its_request():
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    for i in range(5):
        t[0] += 6
        loop.heard(f"people talking {i}")
    assert loop.heard("Andy.") == "Yes?"
    t[0] += 4
    assert loop.heard("where are my glasses") == "ok" and a.heard == ["where are my glasses"]


def test_crisis_words_just_after_a_reply_are_heard_even_with_the_follow_ups_used_up():
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    for i in range(5):
        t[0] += 6
        loop.heard(f"people talking {i}")
    loop.heard("andy what's the weather")
    t[0] += 5
    assert not loop.listening()
    assert loop.heard("I fell and I can't get up") == "ok" and a.heard[-1] == "I fell and I can't get up"


def test_only_the_times_of_speech_not_for_andy_are_kept():
    t = [0.0]
    loop = VoiceLoop(Andy(), clock=lambda: t[0])
    loop.heard("a private conversation about money")
    assert loop._not_for_andy == [0.0]


def test_talk_over_andys_answers_is_a_room_talking_and_ends_a_conversation_already_going():
    """Once follow-ups run, everything is taken, so nothing is 'not for Andy': but a meeting keeps talking over Andy's
    answers, which a person talking with Andy rarely does."""
    t = [0.0]
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=20, clock=lambda: t[0])
    assert loop.heard("hey andy how are you") == "ok"
    t[0] += 10
    for _ in range(5):  # said while Andy was answering the next one (run() counts these)
        loop.not_for_andy()
    assert loop.heard("so the numbers for the quarter") == "ok"  # taken: the window was open
    t[0] += 10
    assert loop.heard("let's move on to the next item") is None  # but not another


def test_a_turn_keeps_its_own_times_listening_again_included():
    """Numbers for the journal's "turn answered" line (where a turn's time went): when the words were heard, how long
    listening again took (a conversation in English is heard again, told no language), when the turn began."""
    import threading

    from heyandy_meta.screen.hood import Hood

    stop, done = threading.Event(), threading.Event()

    class Talking(Andy):
        language, asr_language, hey_only = "en", "eng_Latn", False

        def __init__(self):
            super().__init__()
            self.hood = Hood()

        def notice_language(self, code):
            pass

        def hear(self, text):
            done.set()
            return "ok"

    class Voice:
        language = "eng_Latn"

        def transcribe(self, audio, language=None):
            return "andy how is your day going"

    class Ears:
        active, rate, end_silence_s, floor = False, RATE, 0.5, 0.0

        def feed(self, samples, flag):
            return samples

    def mic(stop):
        yield np.zeros(RATE, np.float32), True, None
        stop.wait(3.0)

    a = Talking()
    loop = VoiceLoop(a)
    threading.Thread(target=loop.run, args=(mic, Voice(), Ears(), stop), daemon=True).start()
    assert done.wait(3.0)
    stop.set()
    m = loop.marks
    assert m["ended"] <= m["heard"] <= m["again"][0] <= m["again"][1] <= m["began"]
    assert a.hood._before and a.hood._before[0][3] == "again"  # waiting for the turn's timeline


def test_while_filming_the_directors_cues_are_heard_without_the_name():
    """November 3: "take two" or "cut" without "Hey Andy" was let go once the follow-up window had closed (or the room
    had talked), so no clap for the edit to line up on. In filming mode those cues alone are heard; nothing else is."""
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=0.0)
    assert loop.heard("take two") is None and a.heard == []  # not filming: a cue is like anything else said
    a.filming = {"since": 0, "takes": []}
    for cue in ("take two", "take 3", "next take", "cut", "that's a wrap"):
        assert loop.heard(cue) == "ok", cue
    assert a.heard == ["take two", "take 3", "next take", "cut", "that's a wrap"]
    assert loop.heard("take the cup off the table") is None and loop.heard("where are my keys") is None
    assert len(a.heard) == 5


def test_an_emergency_or_crisis_words_are_answered_without_the_name():
    """The founder, November 3: someone who has fallen may not say "Hey Andy". Crisis words and an emergency said as the
    sentence itself are answered without the name; the room's talk about falls, rules and the heat is still let go."""
    a = Andy()
    loop = VoiceLoop(a, follow_up_s=0.0)
    for said in ("i fell and i can't get up", "help i've fallen", "my husband just collapsed", "i can't breathe",
                 "i fell in the kitchen last night and i can't get up", "i want to kill myself"):
        assert loop.heard(said) == "ok", said
    for said in ("i fell asleep on the couch", "call 911 if you see smoke", "i can't breathe in this heat",
                 "my son fell off his bike last year", "i can't get up this early anymore", "when grandpa fell they called an ambulance",
                 "where are my keys"):
        assert loop.heard(said) is None, said
