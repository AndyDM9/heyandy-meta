"""Hearing through a microphone on this computer (a PipeWire source: a headset, a webcam) in place of the robot's
array.

November 4, the morning of filming: the robot's microphone array went faint eight times, each reset holding for less
(the device's capture path collapses while its control path answers; docs/system-card.md, Known limits). The
founder's headset is paired with this computer, so Andy hears through it: the same chunks the robot's listening
yields (about 100 ms of 16 kHz mono), a speech flag by loudness, and no direction (Andy faces the person by camera
instead of turning to the voice). Nothing is yielded while Andy speaks, as with the array. The robot still speaks,
moves, finds and points as before.

    HEYANDY_MIC=<PipeWire source name>   (or --mic): pactl list short sources
"""
import subprocess
import time

import numpy as np

RATE = 16000
CHUNK_S = 0.1
SPEECH = 0.01  # a chunk's own loudness (RMS) from which it may be speech: a voice's is 0.04 to 0.14, a quiet room's under 0.01


def command(source: str, rate: int = RATE) -> list[str]:
    """pw-record, mono float32 at Andy's rate, from the named source, to its standard output."""
    return ["pw-record", "--target", source, "--rate", str(rate), "--channels", "1", "--format", "f32", "-"]


def listen_from(source: str, body=None, rate: int = RATE, chunk_s: float = CHUNK_S, popen=subprocess.Popen,
                clock=time.monotonic):
    """A microphone generator like the robot's ``listen``: yields (mono samples, speech flag, direction=None) until
    ``stop`` is set, from the PipeWire source named. With ``body``, nothing is yielded while it speaks."""
    n = int(rate * chunk_s) * 4  # bytes of float32

    def mic(stop):
        p = popen(command(source, rate), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while not stop.is_set():
                buf = p.stdout.read(n)
                if not buf:
                    break  # the source went away (the headset off): listening ends, and the watch says so
                if body is not None and (getattr(body, "speaking", False) or clock() < getattr(body, "_quiet_until", 0)):
                    continue  # Andy's own voice, and the room's echo of it
                samples = np.frombuffer(buf, dtype=np.float32)
                loud = float(np.sqrt(np.mean(np.square(samples)))) if len(samples) else 0.0
                yield samples, loud >= SPEECH, None
        finally:
            p.terminate()

    return mic
