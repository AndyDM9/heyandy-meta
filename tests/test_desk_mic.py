"""Hearing through a microphone on this computer in place of the robot's array (November 4: the array went faint)."""
import io
import threading
from types import SimpleNamespace

import numpy as np

from heyandy_meta.voice.desk_mic import RATE, SPEECH, command, listen_from


class Recorder:
    """A pretend pw-record: its standard output is the samples given, then nothing."""

    def __init__(self, samples):
        self.stdout = io.BytesIO(np.asarray(samples, dtype=np.float32).tobytes())
        self.terminated = False
        self.cmd = None

    def terminate(self):
        self.terminated = True


def test_the_command_records_mono_float32_at_andys_rate():
    assert command("bluez_input.headset") == ["pw-record", "--target", "bluez_input.headset", "--rate", "16000",
                                              "--channels", "1", "--format", "f32", "-"]


def test_chunks_of_a_tenth_of_a_second_with_a_speech_flag_by_loudness_and_no_direction():
    quiet, loud = np.zeros(1600, dtype=np.float32), np.full(1600, 0.05, dtype=np.float32)
    rec = Recorder(np.concatenate([quiet, loud, quiet[:800]]))  # two whole chunks, then a short tail
    made = []
    mic = listen_from("headset", popen=lambda cmd, **kw: made.append(cmd) or rec)
    stop = threading.Event()
    out = list(mic(stop))
    assert made == [command("headset", RATE)]
    assert [(len(s), flag, yaw) for s, flag, yaw in out] == [(1600, False, None), (1600, True, None), (800, False, None)]
    assert rec.terminated  # the recorder is ended when listening ends
    assert SPEECH == 0.01


def test_nothing_is_yielded_while_andy_speaks_or_in_the_echo_after():
    loud = np.full(1600, 0.05, dtype=np.float32)
    rec = Recorder(np.concatenate([loud, loud, loud]))
    body = SimpleNamespace(speaking=True, _quiet_until=0.0)
    t = [0.0]
    mic = listen_from("headset", body=body, popen=lambda cmd, **kw: rec, clock=lambda: t[0])
    chunks = mic(threading.Event())
    body.speaking = False
    body._quiet_until = 10.0  # the room's echo of its own voice, for a moment after
    first = next(chunks, None)  # the first chunk was read while speaking; the second in the echo... the clock says 0
    assert first is None or len(first[0]) == 1600
    # with the clock past the echo, chunks come through again
    rec2 = Recorder(np.concatenate([loud, loud]))
    body2 = SimpleNamespace(speaking=False, _quiet_until=0.0)
    mic2 = listen_from("headset", body=body2, popen=lambda cmd, **kw: rec2, clock=lambda: 5.0)
    assert len(list(mic2(threading.Event()))) == 2


def test_stop_ends_listening_at_once():
    rec = Recorder(np.zeros(16000, dtype=np.float32))
    stop = threading.Event()
    stop.set()
    assert list(listen_from("headset", popen=lambda cmd, **kw: rec)(stop)) == [] and rec.terminated
