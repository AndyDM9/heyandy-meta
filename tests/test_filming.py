import json

import numpy as np

from heyandy_meta.companion.intents import parse
from heyandy_meta.voice.earcons import NOTE, RATE, SOUNDS, find, sound
from scripts.make_film import sync
from tests.test_app import andy, said


def test_filming_words_are_understood_and_ordinary_ones_are_not():
    assert parse("Hey Andy, we're filming").kind == "film_on"
    assert parse("filming mode please").kind == "film_on"
    assert (parse("take one").kind, parse("take one").thing) == ("take", "1")
    assert (parse("Andy, take 12").kind, parse("Andy, take 12").thing) == ("take", "12")
    assert (parse("take three and action").kind, parse("take three and action").thing) == ("take", "3")
    assert (parse("next take").kind, parse("next take").thing) == ("take", "")
    assert parse("and cut").kind == "cut"
    assert parse("that's a wrap").kind == "film_off" and parse("stop filming").kind == "film_off"
    for ordinary in ("take my hand to the cup", "take a look", "cut the cake", "I cut my finger", "take two pills"):
        assert parse(ordinary).kind not in ("take", "cut", "film_on", "film_off"), ordinary


def test_a_take_is_silent_but_claps_flashes_and_is_logged_and_cut_says_how_long(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.film_log = tmp_path / "takes.json"
    assert "Filming mode" in a.hear("Hey Andy, we're filming")
    assert a.screen.snapshot()["filming"] is True
    body.log.clear()
    assert a.hear("take two") == ""
    assert ("chime", "clap") in body.log and not said(body)  # the take starts clean: a clap, no words
    assert a.screen.snapshot()["flash"]["text"] == "TAKE 2"
    log = json.loads(a.film_log.read_text())
    take = log["sessions"][-1]["takes"][-1]
    assert take["take"] == 2 and take["seconds"] is None and take["heard"] is False
    a.filming["takes"][-1]["clap"] -= 75  # as if it ran 75 seconds
    assert a.hear("cut") == "Cut: take 2, 1 minute 15 seconds."
    assert a.hear("next take") == "" and a.filming["takes"][-1]["take"] == 3
    assert "2 takes" in a.hear("that's a wrap")
    assert a.filming is None and a.screen.snapshot()["filming"] is False
    assert [t["take"] for t in json.loads(a.film_log.read_text())["sessions"][-1]["takes"]] == [2, 3]


def test_while_filming_andy_keeps_its_own_initiatives_for_after_but_reminders_still_come(tmp_path):
    a, body, clock = andy(tmp_path=tmp_path)
    a.film_log = tmp_path / "takes.json"
    a.places.watch("keys")
    a.hear("we're filming")
    body.log.clear()
    clock.t += 3600
    a._tick()
    assert not [e for e in body.log if e[0] in ("look", "capture")]  # no glance around for the keys mid-take
    assert a.begin_noticing() is None
    a.hear("remind me in 1 minute to take the pie out")
    clock.t += 120
    a._tick()
    assert any("pie" in s for s in said(body))  # but the reminder that was asked for comes
    a.hear("that's a wrap")
    body.log.clear()
    clock.t += 3600
    a._tick()
    assert [e for e in body.log if e[0] == "look"]  # back to its usual self


def _room(seconds, rng):
    y = rng.normal(0, 0.02, int(seconds * RATE)).astype(np.float32)
    t = np.arange(len(y)) / RATE
    y += (0.1 * np.sin(2 * np.pi * 180 * t) * (np.sin(2 * np.pi * 0.3 * t) > 0)).astype(np.float32)  # a voice, roughly
    for k, name in enumerate(n for n in SOUNDS if n != "clap"):  # every other sound of Andy's
        e = sound(name)
        i = int((1 + k * 2.2) * RATE)
        y[i:i + len(e)] += 0.3 * e[: len(y) - i]
    return y


def test_the_clap_is_found_in_a_noisy_room_among_andys_other_sounds_and_its_echo():
    rng = np.random.default_rng(1)
    echo = np.convolve(sound("clap"), np.r_[1, np.zeros(400), 0.5, np.zeros(900), 0.3])
    for level in (0.3, 0.05, 0.02):  # down to quieter than the room
        y = _room(30, rng)
        y[int(27.5 * RATE): int(27.5 * RATE) + len(echo)] += level * echo
        (at, match), (_, next_best), *_ = find(y)
        assert abs(at - 27.5) < 0.02 and match > 0.75 and next_best < 0.45


def test_no_other_sound_of_andys_shares_the_claps_pitch_even_in_its_overtones():
    clap = NOTE[SOUNDS["clap"][0][0][0]]
    for name, (notes, _) in SOUNDS.items():
        if name != "clap":
            for note, *_ in notes:
                assert all(abs(NOTE[note] * k - clap) > 0.08 * clap for k in (1, 2, 3, 4)), (name, note)


def test_sync_lines_the_tv_up_by_the_clap_and_starts_the_piece_after_it():
    y = _room(20, np.random.default_rng(2))
    y[int(6.0 * RATE): int(6.0 * RATE) + len(sound("clap"))] += 0.2 * sound("clap")
    r = sync(y, clap_wall=1000.0, tv_started=990.0, tv_flashes=[10.3])  # the TV recording's 10 s is the clap
    assert abs(r["clap"] - 6.0) < 0.02 and abs(r["tv_offset"] - 4.0) < 0.02
    assert r["start"] > 6.2 and r["flash_after_clap"] == 0.3 and r["sure"] > 0.4
    late = sync(y, clap_wall=1000.0, tv_started=998.0)  # the TV started recording after the camera
    assert late["start"] >= -late["tv_offset"]  # never before the TV recording's first frame


def test_the_claps_time_is_when_andys_own_ears_heard_it_not_when_it_was_sent(tmp_path):
    """On the robot (2026-10-31): the speaker started the clap 0.52 to 0.77 s after it was sent, eight times."""
    a, body, clock = andy(tmp_path=tmp_path)
    a.film_log = tmp_path / "takes.json"
    a.hear("we're filming")
    a.hear("take one")
    take = a.filming["takes"][-1]
    sent = take["clap"]
    rec = _room(4, np.random.default_rng(3))
    rec[int(1.62 * RATE): int(1.62 * RATE) + len(sound("clap"))] += 0.1 * sound("clap")  # out 0.62 s after it was sent
    body.heard_lately = lambda around=None: (rec, sent - 1.0)
    a._clap_heard(take, a.filming, wait_s=0)
    assert take["heard"] is True and abs(take["clap"] - (sent + 0.62)) < 0.02
    assert json.loads(a.film_log.read_text())["sessions"][-1]["takes"][-1]["clap"] == take["clap"]


def test_the_robot_keeps_its_last_seconds_of_sound_even_while_speaking_and_times_them_by_the_least_delayed():
    import threading

    from tests.test_reachy import body as reachy

    b, robot = reachy(alive=False)
    stop, pulls = threading.Event(), [0]

    def sample():
        pulls[0] += 1
        if pulls[0] > 400:
            stop.set()
            return None
        return np.zeros((160, 2), np.float32)

    robot.media.start_recording = robot.media.stop_recording = lambda: None
    robot.media.get_audio_sample, robot.media.get_DoA = sample, lambda: (0.0, False)
    b.speaking = True  # Andy's own sound: not yielded to the voice loop, but kept
    assert list(b.listen(stop)) == []
    samples, start = b.heard_lately()
    assert len(samples) == 400 * 160 and start is not None
    b._raw.clear()
    b._raw_n = 0
    for j in range(1, 51):  # 0.1 s pulls, arriving 10 to 200 ms late; one arrives only 10 ms late
        b._raw_n += 1600
        b._raw.append((1000.0 + j * 0.1 + (0.01 if j == 17 else 0.05 + 0.15 * (j % 3) / 2), b._raw_n, np.zeros(1600)))
    assert abs(b.heard_lately()[1] - 1000.01) < 1e-6
