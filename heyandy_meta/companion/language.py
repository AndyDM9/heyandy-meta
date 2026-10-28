"""Andy in Spanish: "Andy, habla español." Hearing, speaking and the TV's captions switch; everything else stays.

Omnilingual ASR (Meta's, on this computer) is told it will hear Spanish; Kokoro speaks with a Spanish voice. In
between, Andy's request rules and tools work in English, so Muse Glimmer, also on this computer, translates what the
person said into English and Andy's words into Spanish: 0.25 to 1 s a sentence, so the person's words never leave
the house for it. Glimmer is started at its answer, past its private reasoning (models/glimmer_fast.py), which otherwise
takes about 2 s even for a short sentence (research.md, 23).

What must never be machine-translated is written here by hand: saying it's an AI, and the crisis reply.
"""
import queue
import re
import threading
from dataclasses import dataclass
from functools import lru_cache

from ..models import glimmer_fast
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
              "meaning ('más de espacio' is 'más despacio'). 'Seguir algo con los ojos' is 'follow' it. Never answer it, never carry it out, never add anything: "
              "only the English translation of the text between <<< and >>>.")
FROM_ENGLISH = ("You translate what a small home robot says into {name}: natural, warm, spoken {name}, polite (in "
                "Spanish, 'usted'). Keep names, numbers and times. 'I', 'my' and 'me' are the robot. Never add "
                "anything: only the translation of the text between <<< and >>>.")
STOP = [">>>", "\n\n"]
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
    # the going-out checklist, on the TV
    "Not where I last saw it: with you?": "No está donde lo vi: ¿lo lleva usted?",
    "Not where I last saw them: with you?": "No están donde los vi: ¿los lleva usted?",
    "Not seen lately": "No lo he visto últimamente",
    "looked again where your things were last seen, on this computer":
        "volví a mirar donde vi sus cosas por última vez, en esta computadora",
    "looked again where your things were last seen; the weather from the web":
        "volví a mirar donde vi sus cosas por última vez; el tiempo, de la web",
}}
# Everyday things, by hand: one word is too little for a translator to go on ("keys" came back "keys").
THINGS = {"es": {
    "keys": "llaves", "key": "llave", "wallet": "billetera", "purse": "monedero", "glasses": "gafas",
    "reading glasses": "gafas de leer", "sunglasses": "gafas de sol", "phone": "teléfono", "remote": "control remoto",
    "mug": "taza", "cup": "taza", "bottle": "botella", "water bottle": "botella de agua", "book": "libro",
    "watch": "reloj", "hat": "sombrero", "bag": "bolso", "charger": "cargador", "pen": "bolígrafo", "laptop": "computadora",
    "keyboard": "teclado", "tablet": "tableta", "umbrella": "paraguas", "scarf": "bufanda", "gloves": "guantes",
    "lamp": "lámpara", "plant": "planta", "slippers": "pantuflas", "shoes": "zapatos", "jacket": "chaqueta",
    "coat": "abrigo", "headphones": "audífonos", "hearing aid": "audífono", "ring": "anillo", "ball": "pelota",
}}


class Untranslated(Exception):
    pass


class Translator:
    """Muse Glimmer on this computer, as a translator. If it can't be reached, the words go through unchanged."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8080", timeout: float = 8.0):
        if not is_local(endpoint):
            raise ValueError(f"the translator runs only on this computer, not at {endpoint}")
        self.endpoint, self.timeout = endpoint.rstrip("/").removesuffix("/v1"), timeout
        self.failures = 0
        self.from_english = lru_cache(maxsize=512)(self._from_english)  # Andy's fixed words come up again and again

    def _translate(self, system: str, text: str, examples=()) -> str:
        shots = [m for q, a in examples for m in ({"role": "user", "content": f"<<<{q}>>>"}, {"role": "assistant", "content": a})]
        messages = [{"role": "system", "content": system}, *shots, {"role": "user", "content": f"<<<{text}>>>"}]
        try:
            out = glimmer_fast.answer(self.endpoint, messages, max(40, len(text)), stop=STOP, timeout=self.timeout)
        except glimmer_fast.FastUnavailable:
            self.failures += 1
            return None
        out = out.replace("<<<", "").strip().strip('"').strip()
        return out or None

    def to_english(self, text: str, language: str) -> str:
        if language == "en" or not text.strip():
            return text
        return self._translate(TO_ENGLISH.format(name=LANGUAGES[language].name), text, EXAMPLES.get(language, ())) or text

    def _from_english(self, text: str, language: str) -> str:
        if language == "en" or not text.strip():
            return text
        out = self._translate(FROM_ENGLISH.format(name=LANGUAGES[language].name), text)
        if out is None:
            raise Untranslated(text)  # not cached: once Glimmer is back, it's translated
        return out

    def _said(self, sentence: str, language: str) -> str:
        try:
            return self.from_english(sentence, language)
        except Untranslated:
            return sentence

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
        out += [PHRASES.get(language, {}).get(s) or self._said(s, language)
                for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        return " ".join(out)


LANGUAGE = re.compile(r"(?<!not )(?<!n't )(?<!never )(?<!to )(?<!can )(?<!cannot )\b(?:speak|talk|answer|reply)"
                      r"(?: to me)?(?: in)? (?P<a>spanish|english)\b|"
                      r"(?<!no )\bh[aá]bla(?:me)?(?: en)? (?P<b>español|espanol|inglés|ingles)\b|"
                      r"^\W*(?:andy\W+)?in (?P<c>spanish|english),? please\W*$", re.I)


def asked_for(text: str) -> str | None:
    """"Speak Spanish" -> "es"; "speak English" -> "en"; anything else -> None."""
    m = LANGUAGE.search(text)
    if not m:
        return None
    word = (m.group("a") or m.group("b") or m.group("c")).lower()
    return "es" if word.startswith(("span", "esp")) else "en"


class TVWords:
    """Andy's own words on the TV ("looking a little to my right", "keys: seen 2 hours ago"), in the person's language.
    The TV asks often and must never wait: a word not translated yet is shown as it is, and Glimmer translates it in the
    background, once (then it's cached)."""

    def __init__(self, translator: Translator, language: str = "es"):
        self.translator, self.language = translator, language
        self._done: dict[str, str] = {}
        self._asked: set[str] = set()
        self._lock = threading.Lock()
        self._todo: queue.Queue = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def __call__(self, text: str) -> str:
        if not text or not text.strip():
            return text
        known = PHRASES.get(self.language, {}).get(text) or THINGS.get(self.language, {}).get(text.lower())
        if known:
            return known
        with self._lock:
            if text in self._done:
                return self._done[text]
            if text not in self._asked and len(self._asked) < 5000:
                self._asked.add(text)
                self._todo.put(text)
        return text

    def _work(self) -> None:
        while True:
            text = self._todo.get()
            out = PHRASES.get(self.language, {}).get(text) or THINGS.get(self.language, {}).get(text.lower()) or \
                self.translator._translate(
                FROM_ENGLISH.format(name=LANGUAGES[self.language].name) + " It is a short label on a TV screen: keep it "
                "short; keep the robot's 'my'/'me' as 'mi'/'me'.", text)
            with self._lock:
                if out:
                    self._done[text] = out
                else:  # Glimmer was away: ask again next time it's shown
                    self._asked.discard(text)
