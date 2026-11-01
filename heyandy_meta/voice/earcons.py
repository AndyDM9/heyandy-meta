"""Andy's sounds: short earcons that say "I heard you", "found it", "a reminder" and "noticed" before any words,
and the notes that rise as Andy guides a hand to a thing.

Made here from plain maths (no model, so every model Andy runs is still Meta's): soft-struck notes whose higher
harmonics fade faster than the fundamental, as a marimba bar or a small bell does, all in C major so they sound like
one character. Played on the robot's speaker at 16 kHz, a little below Andy's voice. Pure NumPy.

    uv run python -m heyandy_meta.voice.earcons docs/sounds     # write each one as a WAV, to listen to
"""
import sys

import numpy as np

RATE = 16000
NOTE = {"C5": 523.25, "E5": 659.25, "G5": 783.99, "B5": 987.77, "C6": 1046.50, "D6": 1174.66, "E6": 1318.51, "A6": 1760.00}

# name: [(note, start s, length s, level)], the peak it's scaled to
SOUNDS = {
    "heard": ([("G5", 0.0, 0.26, 0.8), ("C6", 0.075, 0.34, 1.0)], 0.32),  # a quick rising fourth: "yes?"
    "found": ([("C5", 0.0, 0.5, 0.75), ("E5", 0.085, 0.5, 0.8), ("G5", 0.17, 0.5, 0.85), ("C6", 0.255, 0.62, 1.0)],
              0.42),  # a rising run to the octave: "there it is!"
    "reminder": ([("E6", 0.0, 0.5, 0.9), ("C6", 0.2, 0.68, 1.0)], 0.4),  # a gentle bell, falling: "excuse me"
    "noticed": ([("D6", 0.0, 0.32, 1.0)], 0.2),  # one soft note: "I saw that"
    # guiding a hand (companion/guide.py): one short note between the words, up the scale as the hand nears the thing
    "near1": ([("C5", 0.0, 0.2, 1.0)], 0.16), "near2": ([("E5", 0.0, 0.2, 1.0)], 0.18),
    "near3": ([("G5", 0.0, 0.2, 1.0)], 0.2), "near4": ([("C6", 0.0, 0.2, 1.0)], 0.22),
    "near5": ([("E6", 0.0, 0.2, 1.0)], 0.24),
    # filming (app.py film): two quick high notes on a pitch no other sound of Andy's has, even in its overtones, so a
    # camera's recording of the take has one clear mark to line the TV's recording up on (scripts/make_film.py sync)
    "clap": ([("A6", 0.0, 0.1, 1.0), ("A6", 0.14, 0.1, 1.0)], 0.42),
}


def _note(freq: float, seconds: float) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    attack = 1.0 - np.exp(-t / 0.004)  # struck, not clicked
    out = np.zeros_like(t)
    for k, level, fade in ((1, 1.0, 3.2), (2, 0.42, 6.5), (3, 0.16, 11.0), (4, 0.07, 16.0)):  # bright, then warm
        out += level * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * fade)
    tail = np.minimum(1.0, (seconds - t) / 0.03)  # a 30 ms fade at the end: no click when it stops
    return (out * attack * tail).astype(np.float32)


def sound(name: str) -> np.ndarray:
    """The earcon, mono float32 at RATE, peaking at its level (below Andy's voice, which peaks near 0.89)."""
    notes, peak = SOUNDS[name]
    total = max(start + length for _, start, length, _ in notes) + 0.02
    out = np.zeros(int(total * RATE), np.float32)
    for note, start, length, level in notes:
        tone, at = _note(NOTE[note], length) * level, int(start * RATE)
        out[at:at + len(tone)] += tone
    return (out * (peak / float(np.max(np.abs(out))))).astype(np.float32)


def find(samples: np.ndarray, name: str = "clap", rate: int = RATE) -> list[tuple[float, float]]:
    """Where one of these sounds is in a recording: (seconds from its start, match 0 to 1), the best three, a second
    apart. A normalised cross-correlation with the sound, around its notes' pitch only (for the clap, 1.65 to 1.87 kHz,
    where no other sound of Andy's is, even in its overtones; above most of a voice), so the room's hum, speech and the
    other earcons barely match. Used to time filming mode's clap (app.py film; scripts/make_film.py sync)."""
    assert rate == RATE
    ref = sound(name)
    samples = np.asarray(samples, np.float32)
    if len(samples) < len(ref):
        return []
    pitches = [NOTE[note] for note, *_ in SOUNDS[name][0]]
    n = 1 << int(np.ceil(np.log2(len(samples) + len(ref))))
    freqs = np.fft.rfftfreq(n, 1 / rate)
    band = (freqs > min(pitches) * 0.9375) & (freqs < max(pitches) * 1.0625)
    S, R = np.fft.rfft(samples, n) * band, np.fft.rfft(ref, n) * band
    x = np.fft.irfft(S, n)[: len(samples)]
    corr = np.fft.irfft(S * np.conj(R), n)[: len(samples) - len(ref) + 1]
    energy = np.sqrt(np.maximum(np.convolve(x * x, np.ones(len(ref)), "valid"), 1e-12))
    score = corr / (energy * np.sqrt(np.sum(np.fft.irfft(R, n)[: len(ref)] ** 2)) + 1e-9)
    found, taken = [], np.zeros(len(score), bool)
    for _ in range(3):
        i = int(np.argmax(np.where(taken, -np.inf, score)))
        if score[i] <= 0:
            break
        found.append((round(i / rate, 3), round(float(score[i]), 2)))
        taken[max(0, i - rate): i + rate] = True
    return found


def export(folder: str) -> list[str]:
    """Each sound as a 16-bit WAV, for listening (docs/sounds)."""
    import wave
    from pathlib import Path

    Path(folder).mkdir(parents=True, exist_ok=True)
    written = []
    for name in SOUNDS:
        path = Path(folder) / f"andy-{name}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE)
            w.writeframes((sound(name) * 32767).astype("<i2").tobytes())
        written.append(str(path))
    return written


if __name__ == "__main__":
    print("\n".join(export(sys.argv[1] if len(sys.argv) > 1 else "docs/sounds")))
