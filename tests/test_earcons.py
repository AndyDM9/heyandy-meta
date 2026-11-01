import numpy as np
import pytest

from heyandy_meta.robot.sim import Thing
from heyandy_meta.voice.earcons import NOTE, RATE, SOUNDS, sound
from tests.test_app import andy


@pytest.mark.parametrize("name", list(SOUNDS))
def test_each_sound_is_short_clean_and_below_andys_voice(name):
    s = sound(name)
    assert s.dtype == np.float32 and 0.2 <= len(s) / RATE <= 1.3
    assert abs(s[0]) < 1e-3 and abs(s[-1]) < 1e-3  # no click at either end
    assert 0.15 <= np.max(np.abs(s)) <= 0.45  # under Andy's voice, which peaks near 0.89
    spec, f = np.abs(np.fft.rfft(s)), np.fft.rfftfreq(len(s), 1 / RATE)
    # warm, not shrill, on a small speaker; filming's clap is high on purpose (a camera's mark, played once a take)
    assert spec[f > 4000].sum() / spec.sum() < (0.15 if name == "clap" else 0.06)
    loudest = f[np.argmax(spec)]
    assert any(abs(loudest - NOTE[n]) < 8 for n, *_ in SOUNDS[name][0])  # the tune is what sounds


def test_found_chimes_before_the_words_and_a_reminder_chimes_even_in_quiet_time(tmp_path):
    a, body, clock = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.hear("where are my keys")
    log = [e for e in body.log if e[0] in ("chime", "say")]
    found = log.index(("chime", "found"))
    assert any(e[0] == "say" and "keys" in e[1] for e in log[found + 1:])  # the words come after the sound
    a.quiet_until = clock() + 3600
    a.hear("remind me in 1 minute to stretch")
    body.log.clear()
    clock.t += 120
    a.tick()
    assert ("chime", "reminder") in body.log  # asked for: said, with its sound, even while quiet


def test_no_sounds_when_turned_off(tmp_path):
    a, body, _ = andy(Thing("keys", -20.0, 25.0), tmp_path=tmp_path)
    a.sounds = False
    a.hear("where are my keys")
    assert not [e for e in body.log if e[0] == "chime"]


def test_the_name_gets_a_sound_at_once_but_crisis_words_never_do():
    from tests.test_voice import Andy as FakeAndy
    from heyandy_meta.voice.loop import VoiceLoop

    a, chimes = FakeAndy(), []
    a.chime = chimes.append
    loop = VoiceLoop(a)
    loop.heard("Andy, where are my glasses?")
    assert chimes == ["heard"]
    loop.heard("Andy, I want to die")
    assert chimes == ["heard"]  # never a cheerful sound before the crisis reply
