"""Answers with sources: Muse Spark's built-in web search, and the sources it cites shown on the TV.

Andy speaks a short answer and names where it came from ("according to weather.gov"); the TV lists the links. The
model is asked to answer only from what it found, and to say so when it found nothing.
"""
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..budget import WEB_SEARCH, Budget, chat_cost
from ..models.retry import with_retry

INSTRUCTIONS = ("You are Andy, a small tabletop robot in a home in the United States. Answer the question in one or two "
                "short spoken sentences, using only what the web search found, and cite the page you used. Use US "
                "units (Fahrenheit, miles). If it found nothing reliable, say you couldn't find it. No lists, no "
                "markdown, and no web addresses in the words themselves. Never give medical or medication advice; "
                "suggest asking a doctor.")


@dataclass
class Answer:
    text: str
    sources: list[tuple[str, str]] = field(default_factory=list)  # (title, url), in order of first citation

    @property
    def spoken(self) -> str:
        if not self.sources:
            return self.text
        site = urlparse(self.sources[0][1]).netloc.removeprefix("www.")
        return f"{self.text} That's according to {site}."


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"https?://\S+", "", text)
    return " ".join(text.replace("*", "").split())


def _final_text(response) -> str:
    """Only the answer: Muse Spark also writes "commentary" messages while it searches ("I'll get the forecast")."""
    parts = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", "message") != "message" or getattr(item, "phase", None) == "commentary":
            continue
        parts += [getattr(p, "text", "") or "" for p in getattr(item, "content", None) or []]
    return " ".join(p for p in parts if p) or (getattr(response, "output_text", "") or "")


def _citations(response) -> list[tuple[str, str]]:
    seen, out = set(), []
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            for a in getattr(part, "annotations", None) or []:
                if getattr(a, "type", "") == "url_citation" and a.url not in seen:
                    seen.add(a.url)
                    out.append((getattr(a, "title", "") or a.url, a.url))
    return out


def ask(client, question: str, model: str = "muse-spark-1.3", budget: Budget | None = None,
        max_tokens: int = 2000, sleep=time.sleep) -> Answer:
    budget = budget or Budget()
    budget.check(chat_cost(model, 6000, max_tokens) + 2 * WEB_SEARCH)  # it may search and then open a page
    response = with_retry(lambda: client.responses.create(
        model=model, instructions=INSTRUCTIONS, input=question, tools=[{"type": "web_search"}],
        max_output_tokens=max_tokens, reasoning={"effort": "low"}), sleep=sleep)
    usage = getattr(response, "usage", None)
    searches = sum(1 for item in getattr(response, "output", None) or [] if getattr(item, "type", "") == "web_search_call")
    budget.record(model, chat_cost(model, getattr(usage, "input_tokens", 0) or 0,
                                   getattr(usage, "output_tokens", 0) or 0) + max(1, searches) * WEB_SEARCH)
    return Answer(_clean(_final_text(response)), _citations(response))
