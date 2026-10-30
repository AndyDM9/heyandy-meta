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
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.hear("habla español")
    assert a.language == "es" and a.voice.voice == "spa" and a.asr_language == "spa_Latn"
    assert said(body)[0] == DISCLOSURE  # said before the switch, in English
    assert "De acuerdo, desde ahora le hablo en español." in said(body)  # by hand (PHRASES)
    body.log.clear()
    reply = a.hear("¿dónde están mis gafas?")
    assert reply.endswith("I see your glasses, to my right.")  # the rules worked in English
    assert said(body) == ["Déjeme buscar.", "¡Ahí están! Veo sus gafas, a mi derecha."]  # the opener by hand
    assert a.screen.snapshot()["caption"] == "¡Ahí están! Veo sus gafas, a mi derecha."
    a.hear("habla inglés")
    assert a.language == "en" and a.voice.voice == "eng"


def test_the_language_is_remembered(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.hear("speak Spanish")
    b, _, _ = andy(tmp_path=tmp_path)
    b.translator, b.voice = Glimmer(), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    b.load_voice()
    assert b.language == "es" and b.voice.voice == "spa"


def test_the_crisis_reply_in_spanish_is_written_by_hand_and_never_translated(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    glimmer = Glimmer()
    a.translator, a.voice = glimmer, SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
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


@pytest.mark.parametrize("text", ["I don't speak Spanish", "I can't speak Spanish", "how do you say thank you in Spanish, please",
                                  "my neighbour wants to talk in English"])
def test_talking_about_a_language_isnt_switching(text):
    assert asked_for(text) is None


def test_switching_back_restores_the_voice_it_was_started_with(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="af_heart", speed=1.0, loudness=-21.0)
    a.hear("speak Spanish")
    a.hear("speak English")
    assert a.voice.voice == "af_heart"


def test_a_failed_translation_isnt_remembered():
    class Flaky(Glimmer):
        down = True

        def _translate(self, system, text, examples=()):
            return None if self.down else "traducido"

    t = Flaky()
    assert t.spoken("Something new.", "es", DISCLOSURE, CRISIS_REPLY) == "Something new."
    t.down = False
    assert t.spoken("Something new.", "es", DISCLOSURE, CRISIS_REPLY) == "traducido"


@pytest.mark.parametrize("text", ["me quiero matar", "me voy a quitar la vida", "quiero lastimarme", "no quiero estar aquí",
                                  "hacerme dano"])
def test_spanish_crisis_words_are_caught_before_any_model(tmp_path, text):
    a, body, _ = andy(tmp_path=tmp_path)
    glimmer = Glimmer()
    a.translator, a.voice = glimmer, SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.hear("habla español")
    glimmer.asked.clear()
    assert a.hear(text) == CRISIS_REPLY and glimmer.asked == [] and a.device.prompts == []
    assert all(CRISIS_REPLY not in r and text not in q for q, r in a.history)  # not kept for the next chat either


def test_the_tv_shows_andys_words_in_spanish_without_waiting(tmp_path):
    import time as _time

    from heyandy_meta.companion.language import TVWords

    words = TVWords(Glimmer(), "es")
    assert words("keys") == "llaves"  # everyday things by hand, at once
    assert words("Not where I last saw it: with you?").startswith("No está")
    assert words("Let me look.") == "Déjeme buscar."
    assert words("something new") == "something new"  # not yet: shown as it is, translated in the background
    for _ in range(50):
        if words("something new") != "something new":
            break
        _time.sleep(0.01)


def test_the_tv_follows_the_language(tmp_path):
    a, _, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.hear("habla español")
    snap = a.screen.snapshot()
    assert snap["lang"] == "es" and snap["language"].startswith("Español")
    a.places.watch("keys")
    a.refresh_panels()
    assert a.screen.snapshot()["map"][0]["label"] == "llaves"
    a.hear("habla inglés")
    assert a.screen.snapshot()["lang"] == "en" and a.screen.snapshot()["map"][0]["label"] == "keys"
