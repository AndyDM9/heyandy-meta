import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("make_film", Path(__file__).parent.parent / "scripts" / "make_film.py")
film = importlib.util.module_from_spec(spec)
spec.loader.exec_module(film)


def tone(seconds):
    t = np.arange(int(seconds * film.RATE)) / film.RATE
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def quiet(seconds):
    return np.zeros(int(seconds * film.RATE), np.float32)


def test_speech_is_found_and_short_pauses_join_and_long_speech_is_cut_into_readable_pieces():
    sound = np.concatenate([quiet(1), tone(1), quiet(0.2), tone(1), quiet(2), tone(13), quiet(1), tone(0.1)])
    spans = film.speech_spans(sound)
    assert abs(spans[0][0] - 1.0) < 0.05 and abs(spans[0][1] - 3.2) < 0.05  # the 0.2 s pause is one sentence
    assert len(spans) == 4 and all(b - a <= 6.0 for a, b in spans[1:])  # 13 s in three pieces; the click dropped
    assert film.speech_spans(quiet(3)) == []


def test_captions_are_tidied_and_stay_up_long_enough_to_read_without_overlapping():
    assert film.tidy("andy where are my glasses") == "Andy where are my glasses"
    assert film.tidy("i see your keys") == "I see your keys"
    lines = film.readable([(1.0, 1.4, "Let me look"), (2.0, 3.0, "I see your glasses to my right")])
    assert lines[0][1] == 1.95  # wanted 2.2, stopped short of the next line
    assert lines[1] == (2.0, 4.1, "I see your glasses to my right")  # seven words: 2.1 s


def test_srt_round_trips_and_a_cut_piece_is_timed_from_its_own_start():
    lines = [(0.9, 2.43, "Andy where are my glasses"), (64.35, 65.55, "Let me look")]
    text = film.srt(lines)
    assert "00:01:04,350 --> 00:01:05,550" in text
    assert [(round(a, 2), round(b, 2), t) for a, b, t in film.read_srt(text)] == lines
    cut = [(round(a, 2), round(b, 2), t) for a, b, t in film.shifted(lines, 2.0, 65.0)]
    assert cut == [(0.0, 0.43, "Andy where are my glasses"), (62.35, 63.0, "Let me look")]


def test_the_piece_command_keeps_the_take_sound_and_quotes_awkward_paths(tmp_path):
    cmd = film.burn_command(Path("film/take 1.mp4"), Path("film/x.mp4"), Path("film/tv.webm"), 0.8, 12.0, 42.0,
                            "vertical", tmp_path / "it's:here.srt", None)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "vstack" in graph and "1080:1920" in graph and "it\\'s\\:here.srt" in graph
    tv = cmd.index("film/tv.webm")
    assert cmd[tv - 3: tv - 1] == ["-ss", "12.8"]  # the TV starts where the take's piece does
    assert cmd[cmd.index("[v]") + 1: cmd.index("[v]") + 3] == ["-map", "0:a?"]  # the take's own sound


def test_the_captions_leave_out_andys_clap():
    """November 3, a dry run with Andy's own clap and voice: the clap's two notes came out as a caption ("The world war
    I was problem"), and the piece, starting just after the clap, would have flashed it."""
    assert film.without_clap([(1.98, 2.25), (5.1, 6.81)], 2.0) == [(5.1, 6.81)]
    assert film.without_clap([(1.98, 3.4)], 2.0) == [(2.45, 3.4)]  # speech straight after the clap keeps its part
    assert film.without_clap([(1.0, 2.1)], 2.0) == [(1.0, 1.95)]
    assert film.without_clap([(5.1, 6.8)], None) == [(5.1, 6.8)]

