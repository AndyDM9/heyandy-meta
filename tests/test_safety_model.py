from types import SimpleNamespace

import pytest

from heyandy_meta.companion.language import LANGUAGES
from heyandy_meta.companion.safety import CRISIS_REPLY
from heyandy_meta.companion.safety_model import LlamaGuard
from tests.test_app import andy


class Guard:
    """Llama Guard's verdict from a table: what it was asked is kept."""

    def __init__(self, unsafe=()):
        self.unsafe, self.asked = set(unsafe), []

    def self_harm(self, text):
        self.asked.append(text)
        return text in self.unsafe


def test_what_the_word_list_misses_llama_guard_catches_before_any_model(tmp_path):
    said = "honestly everyone would be better off without me around"
    a, body, _ = andy(tmp_path=tmp_path)
    a.guard = Guard([said])
    assert a.hear(said) == CRISIS_REPLY
    assert a.device.prompts == [] and a.history == []  # no model, no history
    assert {m["name"] for m in a.screen.snapshot()["models"]} >= {"Llama Guard 3 (safety check)"}


def test_an_ordinary_turn_goes_on(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.guard = Guard()
    assert "Hello there." in a.hear("how are you today?") and a.guard.asked == ["how are you today?"]


def test_in_spanish_it_reads_the_persons_own_words_before_the_translator(tmp_path):
    from tests.test_language import Glimmer

    said = "creo que todos estarían mejor sin mí"
    a, body, _ = andy(tmp_path=tmp_path)
    glimmer = Glimmer()
    a.translator, a.voice = glimmer, SimpleNamespace(voice="am_michael", speed=1.0, loudness=-21.0)
    a.guard = Guard([said])
    a.hear("habla español")
    glimmer.asked.clear()
    assert a.hear(said) == CRISIS_REPLY and glimmer.asked == []
    assert [e[1] for e in body.log if e[0] == "say"][-1] == LANGUAGES["es"].crisis


def test_the_word_list_doesnt_wait_for_llama_guard(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.guard = Guard()
    assert a.hear("I want to die") == CRISIS_REPLY and a.guard.asked == []


def test_llama_guard_down_means_the_word_list_alone():
    g = LlamaGuard("http://127.0.0.1:9")  # nothing listens there
    assert g.categories("hello") is None and not g.self_harm("hello") and g.unavailable == 2


def test_llama_guard_runs_only_here():
    with pytest.raises(ValueError):
        LlamaGuard("https://api.example.com")
