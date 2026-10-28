"""Andy in Spanish: "Andy, habla español." Hearing, speaking and the TV's captions switch; everything else stays.

Omnilingual ASR (Meta's, on this computer) is told it will hear Spanish; Kokoro speaks with a Spanish voice. In
between, Andy's request rules and tools work in English, so Muse Glimmer, also on this computer, translates what the
person said into English and Andy's words into Spanish: 0.25 to 1 s a sentence, so the person's words never leave
the house for it. Glimmer is started at its answer (" to=user"), past its private reasoning, which otherwise takes
about 2 s even for a short sentence (research.md, 23).

What must never be machine-translated is written here by hand: saying it's an AI, and the crisis reply.
"""
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache

from ..models.common import is_local


@dataclass(frozen=True)
class Language:
    name: str
    asr: str  # Omnilingual ASR's code
    voice: str  # Kokoro's voice: its first letter is the language
    disclosure: str = ""  # said by hand, never translated
    crisis: str = ""


LANGUAGES = {
    "en": Language("English", "eng_Latn", "am_michael"),
    "es": Language("Spanish", "spa_Latn", "em_alex", disclosure="Soy Andy, un robot con inteligencia artificial.",
                   crisis="Soy un robot, así que no puedo ayudarle con esto como lo haría una persona. Puede llamar o "
                          "enviar un mensaje de texto al 988, la Línea de Prevención del Suicidio y Crisis, a cualquier "
                          "hora, de día o de noche; tienen ayuda en español. Si está en peligro ahora mismo, por favor "
                          "llame al 911."),
}

TO_ENGLISH = ("You translate what a person said to their home robot from {name} into English, keeping the meaning, as "
              "the person would say it in English. Commands to the robot stay commands, in these words where they fit: "
              "'where are my ...', 'keep an eye on my ...', 'follow the ...', 'what am I holding?', 'forget my ...', 'remind me at 5 pm to ...', 'remind me in "
              "10 minutes to ...', 'speak more slowly', 'speak up', 'draw me ...', 'show me ... on the TV'. Write times "
              "with digits and am or pm ('a las cinco de la tarde' is 'at 5 pm'). Speech-to-text slips are fixed by "
              "meaning ('más de espacio' is 'más despacio'). Never answer it, never carry it out, never add anything: "
              "only the English translation of the text between <<< and >>>.")
FROM_ENGLISH = ("You translate what a small home robot says into {name}: natural, warm, spoken {name}, polite (in "
                "Spanish, 'usted'). Keep names, numbers and times. 'I', 'my' and 'me' are the robot. Never add "
                "anything: only the translation of the text between <<< and >>>.")
STOP = ["<|eot|>", "<|end|>", "<|start|>", ">>>", "\n\n"]
# Worked examples, so it always answers in English (alone, it sometimes copied the Spanish back unchanged).
EXAMPLES = {"es": (("¿dónde dejé mis llaves?", "Where are my keys?"),
                   ("me voy, ¿llevo todo?", "I'm going out, do I have everything?"))}
# Andy's own short sentences, by hand: too short for a translator to read right ("Let me look" came back "Míreme").
PHRASES = {"es": {
    "Let me look.": "Déjeme buscar.", "Let me see.": "Déjeme ver.", "Let me look that up.": "Déjeme buscarlo.",
    "Let me find that for you.": "Déjeme buscárselo.", "Okay.": "De acuerdo.", "Yes?": "¿Sí?", "Stopped.": "Listo.",
    "Let me check you have everything.": "Déjeme ver si lleva todo.", "Let me replay that.": "Déjeme repasarlo.",
    "It's under this one! Lift it up.": "¡Está debajo de este! Levántelo.", "Have a lovely time!": "¡Que lo pase muy bien!",
    "Let me draw where your things are. It takes a little while.": "Déjeme dibujar dónde están sus cosas. Tarda un poco.",
    "Let me draw that. It takes a little while.": "Déjeme dibujarlo. Tarda un poco.",
    "Okay, I'll speak Spanish now.": "De acuerdo, desde ahora le hablo en español.",
}}


class Translator:
    """Muse Glimmer on this computer, as a translator. If it can't be reached, the words go through unchanged."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8080", timeout: float = 8.0):
        if not is_local(endpoint):
            raise ValueError(f"the translator runs only on this computer, not at {endpoint}")
        self.endpoint, self.timeout = endpoint.rstrip("/").removesuffix("/v1"), timeout
        self.failures = 0
        self.from_english = lru_cache(maxsize=512)(self._from_english)  # Andy's fixed words come up again and again

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.endpoint + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)

    def _translate(self, system: str, text: str, examples=()) -> str:
        shots = [m for q, a in examples for m in ({"role": "user", "content": f"<<<{q}>>>"}, {"role": "assistant", "content": a})]
        try:
            prompt = self._post("/apply-template", {"messages": [{"role": "system", "content": system}, *shots,
                                                                 {"role": "user", "content": f"<<<{text}>>>"}]})["prompt"]
            prompt = prompt.replace("Reasoning strength: high.", "Reasoning strength: low.") + " to=user<|message|>"
            out = self._post("/completion", {"prompt": prompt, "n_predict": max(40, len(text)), "temperature": 0,
                                             "stop": STOP})["content"]
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            self.failures += 1
            return text
        out = out.replace("<<<", "").strip().strip('"').strip()
        return out or text

    def to_english(self, text: str, language: str) -> str:
        if language == "en" or not text.strip():
            return text
        return self._translate(TO_ENGLISH.format(name=LANGUAGES[language].name), text, EXAMPLES.get(language, ()))

    def _from_english(self, text: str, language: str) -> str:
        if language == "en" or not text.strip():
            return text
        return self._translate(FROM_ENGLISH.format(name=LANGUAGES[language].name), text)

    def spoken(self, text: str, language: str, disclosure: str, crisis: str) -> str:
        """Andy's English words in the person's language: the AI disclosure and the crisis reply by hand, each sentence
        translated on its own (most of Andy's sentences are fixed, so most come from the cache)."""
        lang = LANGUAGES[language]
        if language == "en" or not text.strip():
            return text
        if text.strip() == crisis:
            return lang.crisis
        out = []
        if text.startswith(disclosure):
            out.append(lang.disclosure)
            text = text[len(disclosure):]
        if text.strip() in PHRASES.get(language, {}):
            return " ".join(out + [PHRASES[language][text.strip()]])
        out += [PHRASES.get(language, {}).get(s) or self.from_english(s, language)
                for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        return " ".join(out)


LANGUAGE = re.compile(r"\b(?:speak|talk|answer|reply)(?: to me)?(?: in)? (?P<a>spanish|english)\b|"
                      r"\bh[aá]bla(?:me)?(?: en)? (?P<b>español|espanol|inglés|ingles)\b|\bin (?P<c>spanish|english),? please\b",
                      re.I)


def asked_for(text: str) -> str | None:
    """"Speak Spanish" -> "es"; "speak English" -> "en"; anything else -> None."""
    m = LANGUAGE.search(text)
    if not m:
        return None
    word = (m.group("a") or m.group("b") or m.group("c")).lower()
    return "es" if word.startswith(("span", "esp")) else "en"
