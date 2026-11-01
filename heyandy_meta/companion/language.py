"""Andy in the person's language: "Andy, habla español", "Andy, speak Russian". Hearing, speaking and the TV switch;
everything else stays. Spanish first, then thirteen more (companion/languages.py: Mandarin, Tagalog, Vietnamese,
Korean, Russian, Arabic, Hindi, Portuguese, French, Italian, Polish, German, Ukrainian).

Omnilingual ASR (Meta's, on this computer) is told which language it will hear; SeamlessM4T v2 (Meta's) speaks it. In
between, Andy's request rules and tools work in English, so Muse Glimmer, also on this computer, translates what the
person said into English and Andy's words into Spanish: 0.25 to 1 s a sentence, so the person's words never leave
the house for it. Glimmer is started at its answer, past its private reasoning (models/glimmer_fast.py), which otherwise
takes about 2 s even for a short sentence (research.md, 23).

What must never be machine-translated is written by hand: saying it's an AI, and the crisis reply (here for Spanish,
in companion/languages.py for the rest, and the crisis words in companion/safety.py).
"""
import queue
import re
import threading
from dataclasses import dataclass
from functools import lru_cache

from ..models import glimmer_fast
from ..models.common import is_local
from .guide import ES as GUIDE_ES
from .languages import FROM_EN, LINES, MORE, TO_EN
from .languages import THINGS as THING_NAMES


@dataclass(frozen=True)
class Language:
    name: str
    asr: str  # Omnilingual ASR's code
    voice: str  # Meta's voice for the language: eng or spa (local/voice_server.py)
    disclosure: str = ""  # said by hand, never translated
    crisis: str = ""
    native: str = ""  # its own name, on the TV
    here: str = ""  # "on this computer", on the TV beside it


LANGUAGES = {
    "en": Language("English", "eng_Latn", "eng"),
    "es": Language("Spanish", "spa_Latn", "spa", disclosure="Soy Andy, un robot con inteligencia artificial.",
                   crisis="Soy un robot, así que no puedo ayudarle con esto como lo haría una persona. Puede llamar o "
                          "enviar un mensaje de texto al 988, la Línea de Prevención del Suicidio y Crisis, a cualquier "
                          "hora, de día o de noche; tienen ayuda en español. Si está en peligro ahora mismo, por favor "
                          "llame al 911.", native="Español", here="en esta computadora"),
    **{code: Language(row[0], row[2], row[3], disclosure=row[6], crisis=row[7], native=row[1], here=row[4])
       for code, row in MORE.items()},
}

TO_ENGLISH = ("You translate what a person said to their home robot from {name} into English, keeping the meaning, as "
              "the person would say it in English. Commands to the robot stay commands, in these words where they fit: "
              "'where are my ...', 'keep an eye on my ...', 'follow the ...', 'what am I holding?', 'forget my ...', 'remind me at 5 pm to ...', 'remind me in "
              "10 minutes to ...', 'speak more slowly', 'speak up', 'draw me ...', 'show me ... on the TV'. Write times "
              "with digits and am or pm ('a las cinco de la tarde' is 'at 5 pm'). Speech-to-text slips are fixed by "
              "meaning ('más de espacio' is 'más despacio'; in Chinese, 眼睛 'eyes' asked about as lost is 眼镜 'glasses'), "
              "and speech-to-text drops question marks, so a question stays a "
              "question ('se me olvida algo' is 'am I forgetting anything?'). 'Vaso' is a cup, not glasses. "
              "'Seguir algo con los ojos' is 'follow' it. Never answer it, never carry it out, never add anything: "
              "only the English translation of the text between <<< and >>>.")
FROM_ENGLISH = ("You translate what a small home robot says into {name}: natural, warm, spoken {name}, polite, as to "
                "an older person you respect (Spanish 'usted', French 'vous', German 'Sie', Russian and Ukrainian "
                "'вы', Chinese '您'). Keep names, numbers and times. 'I', 'my' and 'me' are the robot. Never add "
                "anything, never leave it in English: only the {name} translation of the text between <<< and >>>.")
STOP = [">>>", "\n\n"]
# Worked examples, so it always answers in English (alone, it sometimes copied the Spanish back unchanged).
EXAMPLES = {"es": (("¿dónde dejé mis llaves?", "Where are my keys?"),
                   ("me voy, ¿llevo todo?", "I'm going out, do I have everything?"))}
# For the other languages, one each way, only when a translation came back unchanged (on Glimmer, Oct 31: one
# Vietnamese request in four, and "Okay." in Vietnamese, Tagalog and Korean). Kept out of the first try: a worked
# example about keys made Glimmer turn "where's my watch" into "where are my keys" (SAID_THINGS, below).
RETRY_TO_EN = {code: ((row[10], TO_EN),) for code, row in MORE.items()}
RETRY_FROM_EN = {code: ((FROM_EN, row[11]),) for code, row in MORE.items()}
# Andy's own short sentences, by hand: too short for a translator to read right ("Let me look" came back "Míreme").
PHRASES = {"es": {
    "Let me look.": "Déjeme buscar.", "Let me look around the room.": "Déjeme mirar la sala.", "Let me see.": "Déjeme ver.", "Let me look that up.": "Déjeme buscarlo.",
    "Let me find that for you.": "Déjeme buscárselo.", "Okay.": "De acuerdo.", "Yes?": "¿Sí?", "Stopped.": "Listo.",
    "Let me check you have everything.": "Déjeme ver si lleva todo.", "Let me replay that.": "Déjeme repasarlo.",
    "It's under this one! Lift it up.": "¡Está debajo de este! Levántelo.", "Have a lovely time!": "¡Que lo pase muy bien!",
    "Let me draw where your things are. It takes a little while.": "Déjeme dibujar dónde están sus cosas. Tarda un poco.",
    "Let me draw that. It takes a little while.": "Déjeme dibujarlo. Tarda un poco.",
    "Okay, I'll speak Spanish now.": "De acuerdo, desde ahora le hablo en español.",
    "Put your hand out toward it, and I'll guide you.": "Extienda la mano hacia allí, y yo le guío.",
    "I can't see your hand.": "No veo su mano.",
    # how a find begins (app.FOUND_OPENERS): no gender, so they fit any thing
    "There it is!": "¡Ahí está!", "Found it!": "¡Listo, ahí está!", "Ah, there it is!": "¡Ah, ahí está!",
    "There they are!": "¡Ahí están!", "Found them!": "¡Listo, ahí están!", "Ah, there they are!": "¡Ah, ahí están!",
    # the going-out checklist, on the TV
    "Not where I last saw it: with you?": "No está donde lo vi: ¿lo lleva usted?",
    "Not where I last saw them: with you?": "No están donde los vi: ¿los lleva usted?",
    "Not seen lately": "No lo he visto últimamente",
    "looked again where your things were last seen, on this computer":
        "volví a mirar donde vi sus cosas por última vez, en esta computadora",
    "looked again where your things were last seen; the weather from the web":
        "volví a mirar donde vi sus cosas por última vez; el tiempo, de la web",
}}
PHRASES["es"].update(GUIDE_ES)  # guiding a hand: "Left.", "A little further.", with no translator between frames
for _code, _row in MORE.items():  # the other languages' short lines, and "Okay, I'll speak it now.", by hand
    PHRASES[_code] = {**dict(zip(LINES, _row[8])), f"Okay, I'll speak {_row[0]} now.": _row[5]}
# Everyday things, by hand: one word is too little for a translator to go on ("keys" came back "keys").
THINGS = {"es": {
    "keys": "llaves", "key": "llave", "wallet": "billetera", "purse": "monedero", "glasses": "gafas",
    "reading glasses": "gafas de leer", "sunglasses": "gafas de sol", "phone": "teléfono", "remote": "control remoto",
    "mug": "taza", "cup": "taza", "bottle": "botella", "water bottle": "botella de agua", "book": "libro",
    "watch": "reloj", "hat": "sombrero", "bag": "bolso", "charger": "cargador", "pen": "bolígrafo", "laptop": "computadora",
    "keyboard": "teclado", "tablet": "tableta", "umbrella": "paraguas", "scarf": "bufanda", "gloves": "guantes",
    "lamp": "lámpara", "plant": "planta", "slippers": "pantuflas", "shoes": "zapatos", "jacket": "chaqueta",
    "coat": "abrigo", "headphones": "audífonos", "hearing aid": "audífono", "ring": "anillo", "ball": "pelota",
}, **{code: dict(zip(THING_NAMES, row[9])) for code, row in MORE.items()}}


# The everyday things in Spanish, to check a translation kept the thing asked for: on the robot (2026-10-31) Glimmer
# turned "Andy, ¿dónde está mi reloj?" into "where are my keys?" three times in three, copying its worked example.
SAID_THINGS = {"es": {
    "keys": ("llave", "llaves", "llavero"), "watch": ("reloj",), "glasses": ("gafas", "lentes", "anteojos", "espejuelos"),
    "phone": ("teléfono", "telefono", "móvil", "movil", "celular"), "wallet": ("cartera", "billetera"),
    "remote": ("control", "mando"), "cup": ("taza", "vaso"), "mug": ("taza",), "bag": ("bolsa", "bolso", "mochila"),
    "book": ("libro",), "pills": ("pastilla", "pastillas"), "bottle": ("botella",), "umbrella": ("paraguas",),
    "pen": ("bolígrafo", "boligrafo", "pluma", "lapicero"), "hat": ("sombrero", "gorra"), "charger": ("cargador",),
    "laptop": ("portátil", "portatil", "laptop"), "keyboard": ("teclado",),
    "headphones": ("auriculares", "audífonos", "audifonos", "cascos")}}


def kept_the_thing(said: str, english: str, language: str) -> str:
    """If the translation names an everyday thing the person didn't say, and they named exactly one other, use theirs."""
    things = SAID_THINGS.get(language)
    if not things:
        return english
    heard = re.findall(r"\w+", said.lower())
    in_said = {t for t, words in things.items() if any(w in heard for w in words)}
    named = [t for t in things if re.search(rf"\b{t}\b", english, re.I)]
    wrong = [t for t in named if t not in in_said]
    if len(wrong) == 1 and len(in_said) == 1 and not set(named) & in_said:
        return re.sub(rf"\b{wrong[0]}\b", next(iter(in_said)), english, flags=re.I)
    return english


class Untranslated(Exception):
    pass


def unchanged(text: str, out: str) -> bool:
    """A translation that came back as it went in (letters only, any case)."""
    letters = lambda x: re.sub(r"\W+", "", x).casefold()  # noqa: E731
    return letters(text) == letters(out)


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
        system = TO_ENGLISH.format(name=LANGUAGES[language].name)
        out = self._translate(system, text, EXAMPLES.get(language, ()))
        if out is not None and unchanged(text, out) and language in RETRY_TO_EN:
            out = self._translate(system, text, RETRY_TO_EN[language]) or out  # copied back: once more, shown how
        return kept_the_thing(text, out, language) if out else text

    def _from_english(self, text: str, language: str) -> str:
        if language == "en" or not text.strip():
            return text
        system = FROM_ENGLISH.format(name=LANGUAGES[language].name)
        out = self._translate(system, text)
        if out is not None and unchanged(text, out) and language in RETRY_FROM_EN:
            out = self._translate(system, text, RETRY_FROM_EN[language]) or out
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


NAMES = {"english": "en", "spanish": "es", **{row[0].lower(): code for code, row in MORE.items()},
         "mandarin": "zh", "filipino": "tl"}
LANGUAGE = re.compile(r"(?<!not )(?<!n't )(?<!never )(?<!to )(?<!can )(?<!cannot )\b(?:speak|talk|answer|reply)"
                      r"(?: to me)?(?: in)? (?P<a>" + "|".join(NAMES) + r")\b|"
                      r"(?<!no )\bh[aá]bla(?:me)?(?: en)? (?P<b>español|espanol|inglés|ingles)\b|"
                      r"^\W*(?:andy\W+)?in (?P<c>" + "|".join(NAMES) + r"),? please\W*$|"
                      # "Say English" (Chinese 说英语, word for word): only the whole request, never "I'd say French is..."
                      r"^\W*(?:andy\W+)?say (?:it )?(?:in )?(?P<d>" + "|".join(NAMES) + r")\W*$", re.I)


def asked_for(text: str) -> str | None:
    """"Speak Spanish" -> "es"; "speak Russian" -> "ru"; "speak English" -> "en"; anything else -> None."""
    m = LANGUAGE.search(text)
    if not m:
        return None
    word = (m.group("a") or m.group("b") or m.group("c") or m.group("d")).lower()
    return "es" if word.startswith("esp") else "en" if word.startswith("ingl") else NAMES[word]


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
                "short; the robot's own 'my' and 'me' stay the robot's.", text)
            with self._lock:
                if out:
                    self._done[text] = out
                else:  # Glimmer was away: ask again next time it's shown
                    self._asked.discard(text)
