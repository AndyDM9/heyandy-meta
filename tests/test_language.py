from types import SimpleNamespace

import pytest

from heyandy_meta.companion.language import LANGUAGES, Translator, asked_for
from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE
from heyandy_meta.robot.sim import Thing
from tests.test_app import andy

SPANISH = {"Okay, I'll speak Spanish now.": "De acuerdo, ahora hablaré español.", "Let me look.": "Déjeme mirar.",
           "I see your glasses, to my right.": "Veo sus gafas, a mi derecha."}
ENGLISH = {"habla español": "speak Spanish", "¿dónde están mis gafas?": "where are my glasses?",
           "habla inglés": "speak English"}


class Glimmer(Translator):
    """The translator, with Glimmer's answers from a table: what was asked is kept."""

    def __init__(self):
        super().__init__()
        self.asked = []

    def _translate(self, system, text, examples=()):
        self.asked.append(text)
        table = ENGLISH if "into English" in system else SPANISH
        return table.get(text, text)


@pytest.mark.parametrize("text,to", [("speak Spanish", "es"), ("Andy, habla español", "es"), ("talk to me in English", "en"),
                                     ("háblame en inglés", "en"), ("in Spanish, please", "es"), ("where are my keys", None)])
def test_asking_for_a_language(text, to):
    assert asked_for(text) == to


def said(body):
    return [e[1] for e in body.log if e[0] == "say"]


def test_andy_hears_and_speaks_spanish(tmp_path):
    a, body, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="am_michael", speed=1.0, loudness=-21.0)
    a.hear("habla español")
    assert a.language == "es" and a.voice.voice == "em_alex" and a.asr_language == "spa_Latn"
    assert said(body)[0] == DISCLOSURE  # said before the switch, in English
    assert "De acuerdo, desde ahora le hablo en español." in said(body)  # by hand (PHRASES)
    body.log.clear()
    reply = a.hear("¿dónde están mis gafas?")
    assert reply.endswith("I see your glasses, to my right.")  # the rules worked in English
    assert said(body) == ["Déjeme buscar.", "Veo sus gafas, a mi derecha."]
    assert a.screen.snapshot()["caption"] == "Veo sus gafas, a mi derecha."
    a.hear("habla inglés")
    assert a.language == "en" and a.voice.voice == "am_michael"


def test_the_language_is_remembered(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="am_michael", speed=1.0, loudness=-21.0)
    a.hear("speak Spanish")
    b, _, _ = andy(tmp_path=tmp_path)
    b.translator, b.voice = Glimmer(), SimpleNamespace(voice="am_michael", speed=1.0, loudness=-21.0)
    b.load_voice()
    assert b.language == "es" and b.voice.voice == "em_alex"


def test_the_crisis_reply_in_spanish_is_written_by_hand_and_never_translated(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    glimmer = Glimmer()
    a.translator, a.voice = glimmer, SimpleNamespace(voice="am_michael", speed=1.0, loudness=-21.0)
    a.hear("habla español")
    glimmer.asked.clear()
    reply = a.hear("ya no quiero vivir")
    assert reply == CRISIS_REPLY and said(body)[-1] == LANGUAGES["es"].crisis and "988" in said(body)[-1]
    assert glimmer.asked == []  # the person's words went to no model, not even the local translator
    assert a.device.prompts == []


def test_without_a_translator_andy_stays_in_english(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    assert "only speak English" in a.hear("habla español") and a.language == "en"


def test_spoken_keeps_the_disclosure_by_hand():
    out = Glimmer().spoken(DISCLOSURE + " Let me look.", "es", DISCLOSURE, CRISIS_REPLY)
    assert out == LANGUAGES["es"].disclosure + " Déjeme buscar."


def test_the_translator_only_runs_here():
    with pytest.raises(ValueError):
        Translator("https://api.example.com")


def test_the_voice_loop_tells_asr_the_language():
    from heyandy_meta.voice.loop import STOP, WAKE

    assert WAKE.match("oye Andy, ¿dónde están mis llaves?") and STOP.search("basta")
