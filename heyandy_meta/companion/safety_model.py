"""A second crisis check, on this computer: Llama Guard 3 (Meta's open weights) reads what the person said.

The word list in safety.py catches the ways people usually say it, in English and Spanish, instantly. People also say
it in ways no list has ("everyone would be better off without me"). Llama Guard's self-harm category (S11) is trained
for that, so it reads every turn too, before any other model sees the words, the translator included. Only S11
matters here: it turns the reply into the crisis reply (988), the same as the word list. Llama Guard's other
categories aren't Andy's to act on.

It runs in its own llama-server on GPU 1 (deploy/heyandy-guard.service), on 127.0.0.1 only; if it's down, the word
list still stands (and the turn says nothing about it).
"""
import json
import time
import urllib.error
import urllib.request

from ..models.common import is_local

SELF_HARM = "S11"


class LlamaGuard:
    def __init__(self, endpoint: str = "http://127.0.0.1:8094", timeout: float = 3.0):
        if not is_local(endpoint):
            raise ValueError(f"the safety check runs on this computer, not at {endpoint}")
        self.endpoint, self.timeout = endpoint.rstrip("/"), timeout
        self.unavailable, self.last_s = 0, 0.0

    def categories(self, text: str) -> list[str] | None:
        """Llama Guard's unsafe categories for what the person said ([] if safe); None if it couldn't be asked."""
        body = json.dumps({"messages": [{"role": "user", "content": text[:2000]}], "max_tokens": 12, "temperature": 0})
        req = urllib.request.Request(self.endpoint + "/v1/chat/completions", body.encode(),
                                     {"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.load(r)["choices"][0]["message"]["content"] or ""
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
            self.unavailable += 1
            return None
        finally:
            self.last_s = time.monotonic() - start
        words = out.strip().split()
        if not words or words[0].lower() != "unsafe":
            return []
        return [c.strip(",") for c in words[1:] if c.strip(",").startswith("S")]

    def self_harm(self, text: str) -> bool:
        return SELF_HARM in (self.categories(text) or [])


# A third look, for conversation only (never a request like "where are my keys?"): Muse Glimmer on this computer,
# asked one narrow question, deterministically (temperature 0). Llama Guard 3 and the word lists missed every one of
# 45 warning signs written in ways no list has ("I won't be around much longer", "there's no way out for me"), in
# fifteen languages; Glimmer caught 16 of them, and none of 40 everyday remarks built to trick it ("I'd kill for a
# coffee", "I won't be around this weekend", "there's no way out of this traffic") (evals/crisis_languages.py,
# docs/research.md section 58). Of two wordings tried, this one; the other, framed as "a safety check", caught none.
CHECK = ("You check what a person said to a home robot, for one thing only. Answer yes if it suggests they may be "
         "thinking about ending their life or harming themselves, even said indirectly; answer no for anything else, "
         "including figures of speech, tiredness, illness, grief and everyday plans. Answer with one word: yes or no.")


class GlimmerCheck:
    def __init__(self, endpoint: str = "http://127.0.0.1:8080", timeout: float = 4.0):
        if not is_local(endpoint):
            raise ValueError(f"the safety check runs on this computer, not at {endpoint}")
        self.endpoint, self.timeout, self.last_s = endpoint.rstrip("/").removesuffix("/v1"), timeout, 0.0

    def self_harm(self, text: str) -> bool:
        """Yes or no; no if Glimmer can't be asked (the other checks still stand)."""
        from ..models import glimmer_fast

        start = time.monotonic()
        try:
            out = glimmer_fast.answer(self.endpoint, [{"role": "system", "content": CHECK}, {"role": "user", "content": text}],
                                      3, timeout=self.timeout)
        except glimmer_fast.FastUnavailable:
            return False
        finally:
            self.last_s = time.monotonic() - start
        return (out or "").strip().lower().startswith("yes")
