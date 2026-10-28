from types import SimpleNamespace as NS

import pytest

from heyandy_meta.companion import web
from heyandy_meta.companion.intents import parse
from tests.test_app import andy


def test_typing_personal_details_is_refused():
    page = "https://www.allrecipes.com/recipe/1"
    assert web.review([{"type": "type", "text": "banana bread"}], page) is None
    for text in ("me@example.com", "305 555 0199 2", "4111 1111 1111 1111", "my password is"):
        assert web.review([{"type": "type", "text": text}], page)
    assert web.review([{"type": "keypress", "keys": ["ctrl", "l"]}], page) is None
    assert web.review([{"type": "keypress", "keys": ["ctrl", "s"]}], page)


@pytest.mark.parametrize("url", ["https://shop.example.com/checkout", "https://example.com/account/settings",
                                 "https://accounts.example.com/signin?next=/", "https://example.com/cart"])
def test_sign_in_and_payment_pages_end_the_run(url):
    assert "sign-in" in web.review([], url)


def test_an_ordinary_page_with_words_like_those_is_fine():
    assert web.review([], "https://en.wikipedia.org/wiki/Shopping_cart") is None  # "cart" in a title, not a path step


def test_typed_addresses_and_searches():
    assert web.address("en.wikipedia.org/wiki/Sunny_Isles_Beach") == "https://en.wikipedia.org/wiki/Sunny_Isles_Beach"
    assert web.address("banana bread") == web.SEARCH + "banana+bread"


class Browser:
    def __init__(self, urls=None):
        self.done, self.urls, self.opened = [], list(urls or []), None

    def screenshot(self):
        return b"jpeg"

    def url(self):
        return self.urls[0] if self.urls else "https://www.allrecipes.com/recipe/1"

    def execute(self, actions):
        self.done.append(actions)
        if self.urls:
            self.urls.pop(0)

    def open(self, url):
        self.opened = url

    def search(self, words):
        self.opened = web.address(words)


def call(*actions, checks=()):
    return NS(type="computer_call", call_id="c1", actions=[dict(a) for a in actions],
              pending_safety_checks=[{"id": f"s{i}", "code": "computer_action_requires_confirmation", "message": "ok"}
                                     for i in range(len(checks))])


def message(text):
    return NS(type="message", content=[NS(text=text)])


class Spark:
    """Answers each Responses call in turn, and keeps what it was sent."""

    def __init__(self, *outputs):
        self.outputs, self.sent = list(outputs), []
        self.responses = self

    def create(self, **kw):
        self.sent.append(kw)
        return NS(id=f"r{len(self.sent)}", output=self.outputs.pop(0), usage=NS(input_tokens=1000, output_tokens=50))


def test_a_run_reviews_then_acknowledges_each_safety_check():
    spark = Spark([call({"type": "scroll", "x": 600, "y": 400, "scroll_y": 500}, checks=[1])],
                  [message("I'll scroll. The ingredients are on the TV now.")])
    steps = []
    run = web.use_the_web(spark, Browser(), "scroll to the ingredients", lambda j, w, p: steps.append(w))
    assert run.steps == 1 and run.answer == "I'll scroll. The ingredients are on the TV now."
    ack = spark.sent[1]["input"][0]
    assert ack["acknowledged_safety_checks"][0]["id"] == "s0" and ack["call_id"] == "c1"
    assert spark.sent[1]["previous_response_id"] == "r1" and "Scrolling" in steps


def test_a_run_stops_before_typing_something_personal():
    spark = Spark([call({"type": "type", "text": "me@example.com"}, checks=[1])])
    b = Browser()
    run = web.use_the_web(spark, b, "sign me up", lambda *a: None)
    assert "personal" in run.stopped and b.done == []  # nothing ran


def test_a_click_that_lands_on_a_sign_in_page_goes_back_and_stops():
    spark = Spark([call({"type": "click", "x": 10, "y": 10}, checks=[1])])
    b = Browser(urls=["https://news.example.com/story", "https://news.example.com/login"])
    run = web.use_the_web(spark, b, "read the story", lambda *a: None)
    assert "sign-in" in run.stopped and b.done[-1] == [{"type": "keypress", "keys": ["alt", "left"]}]


def test_a_follow_up_sends_words_only():
    spark = Spark([message("Done.")])
    web.use_the_web(spark, Browser(), "scroll down", lambda *a: None, previous="r9")
    sent = spark.sent[0]
    assert sent["previous_response_id"] == "r9"
    assert [c["type"] for c in sent["input"][0]["content"]] == ["input_text"]


@pytest.mark.parametrize("text", ["show me a banana bread recipe on the TV", "put the weather radar on the screen",
                                  "show me pictures of the northern lights", "open wikipedia"])
def test_asking_for_the_web(text):
    assert parse(text).kind == "web"


@pytest.mark.parametrize("text,kind", [("what's the weather tomorrow", "world"), ("find my keys", "find"),
                                       ("draw me a cat", "draw")])
def test_other_requests_stay_where_they_were(text, kind):
    assert parse(text).kind == kind


def test_andy_shows_a_page_and_takes_follow_ups(tmp_path, monkeypatch):
    spark = Spark([message("The recipe is on the TV.")], [message("Scrolled to the ingredients.")])
    a, body, _ = andy(spark=spark, tmp_path=tmp_path)
    a._browser = Browser()
    monkeypatch.setattr(web, "best_page", lambda *a, **k: "https://www.allrecipes.com/recipe/1")
    reply = a.hear("show me a banana bread recipe on the TV")
    assert "The recipe is on the TV." in reply and a._browser.opened == "https://www.allrecipes.com/recipe/1"
    snap = a.screen.snapshot()
    assert snap["web"]["host"] == "allrecipes.com" and snap["source"] == "cloud"
    assert any("screenshots of the web page" in o["words"] for o in snap["outbox"])  # the privacy receipt says so
    assert "Scrolled to the ingredients." in a.hear("scroll down")
    assert spark.sent[-1]["previous_response_id"] == "r1"
    assert "closed" in a.hear("close the browser") and a.screen.snapshot()["web"] is None


def test_offline_andy_says_the_web_needs_a_connection(tmp_path):
    a, _, _ = andy(online=False, tmp_path=tmp_path)
    assert "when I'm connected" in a.hear("show me the weather radar on the TV")
