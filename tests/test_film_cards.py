import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import film_cards  # noqa: E402


def test_the_figures_come_from_the_files_and_say_what_they_say():
    figs = {f["from"]: f["big"] for f in film_cards.figures()}
    assert figs["evals/results/unattended-*"] == "206 of 208"  # since the aim fix; both misses (the keys, Nov 1) kept
    assert figs["unattended-20261101-2231"] == "0.9°"  # the final code: focus held, the true ray, the head read back
    judged = [f for f in film_cards.figures() if f["from"].startswith("physical-fixed-")]
    assert judged and "never at the wrong thing" in judged[0]["line"]  # a person's verdicts, second on the card
    assert film_cards.figures()[1] is not None and film_cards.figures()[1]["from"].startswith("physical-fixed-")
    assert figs["privacy-audit"].startswith("0 of ")
    assert all(f["line"] and f["from"] for f in film_cards.figures())


def test_a_figure_the_files_dont_support_stops_the_render(monkeypatch):
    real = film_cards._load

    def leaky(name):
        data = real(name)
        if name == "privacy-audit.json":
            data["summary"] = {**data["summary"], "camera_pictures_to_cloud": 1}
        return data

    monkeypatch.setattr(film_cards, "_load", leaky)
    with pytest.raises(SystemExit, match="privacy-audit"):
        film_cards.figures()


def test_each_card_has_its_words_and_a_length():
    for body, seconds in (film_cards.title(film_cards.LINE), film_cards.numbers(film_cards.figures()), film_cards.end()):
        assert 5 <= seconds <= 30 and "<" in body
    assert "Before this week" in film_cards.title(film_cards.LINE)[0]
    assert film_cards.DEMO in film_cards.end()[0]
