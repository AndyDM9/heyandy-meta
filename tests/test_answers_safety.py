from types import SimpleNamespace

import pytest

from heyandy_meta.budget import Budget, BudgetExceeded
from heyandy_meta.companion.answers import Answer, ask
from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE, Disclosure, crisis, respond


class SparkWithSearch:
    def __init__(self, text, cites):
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)
        self._text, self._cites = text, cites

    def _create(self, **kw):
        self.calls.append(kw)
        anns = [SimpleNamespace(type="url_citation", url=u, title=t) for t, u in self._cites]
        return SimpleNamespace(output_text=self._text, usage=SimpleNamespace(input_tokens=2000, output_tokens=60),
                               output=[SimpleNamespace(content=[SimpleNamespace(annotations=anns)])])


def test_answer_names_its_source_and_lists_links():
    spark = SparkWithSearch("Yes, the market is open **Saturday** 8 to noon ([site](https://x.org)).",
                            [("Farmers market", "https://www.townmarket.org/hours"), ("Farmers market", "https://www.townmarket.org/hours")])
    a = ask(spark, "Is the farmers market open Saturday?", budget=Budget())
    assert a.text == "Yes, the market is open Saturday 8 to noon (site)."
    assert a.sources == [("Farmers market", "https://www.townmarket.org/hours")]
    assert a.spoken.endswith("That's according to townmarket.org.")
    assert spark.calls[0]["tools"] == [{"type": "web_search"}] and spark.calls[0]["model"] == "muse-spark-1.3"


def test_search_is_charged_on_top_of_tokens():
    budget = Budget()
    ask(SparkWithSearch("ok", []), "q", budget=budget)
    assert budget.spent() == pytest.approx((2000 * 1.25 + 60 * 4.25) / 1e6 + 0.0025)


def test_no_sources_no_claim():
    assert Answer("I couldn't find that.").spoken == "I couldn't find that."


def test_paid_calls_off_means_no_search(monkeypatch):
    monkeypatch.delenv("HEYANDY_PAID_CALLS")
    spark = SparkWithSearch("x", [])
    with pytest.raises(BudgetExceeded):
        ask(spark, "q")
    assert spark.calls == []


@pytest.mark.parametrize("text", ["I want to kill myself", "sometimes I don't want to live anymore",
                                  "I've been thinking about suicide", "I want to hurt myself"])
def test_crisis_words_get_the_fixed_reply_and_never_reach_the_model(text):
    asked = []
    reply = respond(text, lambda t: asked.append(t) or "model", Disclosure(clock=lambda: 0.0))
    assert reply == CRISIS_REPLY and "988" in reply and asked == []


@pytest.mark.parametrize("text", ["where are my glasses", "this battery is killing me", "I could die for a coffee"])
def test_ordinary_words_are_not_crises(text):
    assert not crisis(text)


def test_says_its_an_ai_at_the_start_and_every_three_hours():
    t = [0.0]
    d = Disclosure(clock=lambda: t[0])
    assert respond("hello", lambda s: "Hi!", d) == DISCLOSURE + " Hi!"
    t[0] = 600
    assert respond("time?", lambda s: "Ten past.", d) == "Ten past."
    for minute in range(10, 3 * 60 + 1, 10):  # a conversation that never goes quiet for half an hour
        t[0] = minute * 60
        reply = respond("and now?", lambda s: "ok", d)
    assert reply.startswith(DISCLOSURE)
    t[0] += 31 * 60
    assert respond("back again", lambda s: "ok", d).startswith(DISCLOSURE)  # a new conversation


def test_only_the_final_answer_is_spoken_not_the_commentary():
    from types import SimpleNamespace as NS

    from heyandy_meta.companion.answers import ask

    cite = NS(type="url_citation", url="https://www.weather.gov/mia", title="Miami forecast")
    resp = NS(output_text="I'll get the forecast.Sunny, 84.", usage=None, output=[
        NS(type="message", phase="commentary", content=[NS(text="I'll get the forecast.", annotations=[])]),
        NS(type="web_search_call"), NS(type="web_search_call"),
        NS(type="message", phase=None, content=[NS(text="Sunny tomorrow, high of 84.", annotations=[cite])])])
    client = NS(responses=NS(create=lambda **kw: resp))
    a = ask(client, "weather tomorrow?")
    assert a.text == "Sunny tomorrow, high of 84." and a.sources == [("Miami forecast", "https://www.weather.gov/mia")]


@pytest.mark.parametrize("text", ["I want to take my own life", "I wanna die", "I don’t want to live anymore",
                                  "I wish I was dead", "life isn't worth living", "there's no reason to live",
                                  "sería mejor estar muerto", "quisiera morirme", "me dan ganas de morirme"])
def test_more_ways_of_saying_it(text):
    from heyandy_meta.companion.safety import crisis

    assert crisis(text)


@pytest.mark.parametrize("text", ["I'm dying to see the new film", "this bread is to die for", "kill the lights please",
                                  "my phone died", "the plant is dead"])
def test_everyday_words_arent_a_crisis(text):
    from heyandy_meta.companion.safety import crisis

    assert not crisis(text)


def test_a_chat_reply_saying_andy_cant_see_or_find_things_is_replaced_and_ordinary_cants_are_not():
    """Offline, Glimmer answered a misheard "where's the remote?" with "I can't see or move around to find things"
    (Nov 1 rehearsal): untrue of Andy. Only claims about the robot's own senses and body are replaced."""
    from heyandy_meta.app import CANT

    for said in ["I can't see or move around to find things, so I can't check on the remote.", "I'm not able to look around.",
                 "I don't have eyes, sadly.", "I can't find things in your house.", "I cannot see your room."]:
        assert CANT.search(said), said
    for said in ["I can't find a good recipe for that.", "I cannot see the future.", "I can't wait to see you",
                 "I can't see why not!", "I can't remember that day."]:
        assert not CANT.search(said), said
