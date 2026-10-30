"""Text as Meta's voices can say it: numbers, times and units in words; for MMS-TTS also phrases with their pauses.

MMS-TTS (Meta's open text-to-speech, the voice the rules allow: every model Andy runs is Meta's) reads lowercase
letters and little else: its English alphabet has no punctuation and only the digits 0 to 6. So numbers, times and
units become words here, a few abbreviations are spelled the way they're said, and the text is cut at its
punctuation into phrases, each followed by the silence a person would leave. Pure Python, for the voice server.
"""
import re

ONES = {"en": "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
              "seventeen eighteen nineteen".split(),
        "es": "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis "
              "diecisiete dieciocho diecinueve".split()}
TENS = {"en": ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"],
        "es": ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]}
ES_TWENTIES = ["veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
               "veintisiete", "veintiocho", "veintinueve"]
ES_HUNDREDS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos",
               "ochocientos", "novecientos"]

SAID_AS = {"en": {"ai": "A I", "tv": "T V", "ok": "okay", "am": "A M", "pm": "P M", "mph": "miles an hour",
                  "°f": "degrees", "°c": "degrees", "°": "degrees", "%": "percent", "&": "and", "ft": "feet",
                  "km": "kilometers", "mi": "miles", "vs": "versus", "etc": "and so on", "sam": "Sam"},
           "es": {"ai": "I A", "ia": "I A", "tv": "tele", "ok": "vale", "am": "de la mañana", "pm": "de la tarde",
                  "°c": "grados", "°f": "grados", "°": "grados", "%": "por ciento", "&": "y", "km": "kilómetros",
                  "m": "metros"}}
LETTERS = {"en": dict(zip("abcdefghijklmnopqrstuvwxyz", "ay bee see dee ee ef gee aitch eye jay kay el em en oh pee "
                                                         "cue ar ess tee you vee double-you ex why zee".split())),
           "es": dict(zip("abcdefghijklmnopqrstuvwxyz", "a be ce de e efe ge hache i jota ka ele eme ene o pe cu "
                                                         "erre ese te u uve uve-doble equis i-griega zeta".split()))}

PAUSES = {",": 0.15, ";": 0.2, ":": 0.2, "—": 0.2, "–": 0.2, ".": 0.32, "!": 0.32, "?": 0.38}


def number(n: int, lang: str = "en") -> str:
    """0 to 999,999 in words."""
    if n < 0:
        return ("minus " if lang == "en" else "menos ") + number(-n, lang)
    if n < 20:
        return ONES[lang][n]
    if n < 100:
        if lang == "es" and n < 30:
            return ES_TWENTIES[n - 20]
        t, o = divmod(n, 10)
        return TENS[lang][t] + ("" if not o else ("-" if lang == "en" else " y ") + ONES[lang][o])
    if n < 1000:
        h, rest = divmod(n, 100)
        if lang == "en":
            return ONES["en"][h] + " hundred" + (" " + number(rest, lang) if rest else "")
        return ("cien" if n == 100 else ES_HUNDREDS[h]) + (" " + number(rest, lang) if rest else "")
    th, rest = divmod(n, 1000)
    head = ("mil" if th == 1 else number(th, lang) + " mil") if lang == "es" else number(th, lang) + " thousand"
    return head + (" " + number(rest, lang) if rest else "")


def _time(h: int, m: int, lang: str) -> str:
    if lang == "es":
        return number(h, lang) + ("" if not m else " y " + number(m, lang))
    return number(h, lang) + (" o'clock" if not m else " oh " + number(m, lang) if m < 10 else " " + number(m, lang))


def words(text: str, lang: str = "en") -> str:
    """Numbers, times and units in words; abbreviations as they're said."""
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda m: _time(int(m[1]), int(m[2]), lang), text)
    text = re.sub(r"(\d+)\.(\d+)", lambda m: number(int(m[1]), lang) + (" point " if lang == "en" else " coma ")
                  + " ".join(number(int(d), lang) for d in m[2]), text)
    text = re.sub(r"(\d+),(\d{3})\b", r"\1\2", text)  # 1,500 -> 1500
    text = re.sub(r"\d+", lambda m: number(int(m[0]), lang) if len(m[0]) <= 6 else
                  " ".join(number(int(d), lang) for d in m[0]), text)
    said = SAID_AS.get(lang, {})
    text = re.sub(r"°[fFcC]?|%|&", lambda m: " " + said.get(m[0].lower(), "") + " ", text)
    text = re.sub(r"\b[A-Za-z]{1,3}\b", lambda m: said.get(m[0].lower(), m[0]), text)
    text = re.sub(r"\b[A-Z]{2,4}\b", lambda m: " ".join(LETTERS[lang][c.lower()] for c in m[0]), text)  # USB
    return re.sub(r"\s+", " ", text).strip()


def phrases(text: str, lang: str = "en") -> list[tuple[str, float]]:
    """The text cut at its punctuation: each phrase in words, and the pause after it (seconds)."""
    out = []
    for part, mark in re.findall(r"([^,;:.!?—–]+)([,;:.!?—–]*)", text):
        said = words(part, lang)
        if not re.search(r"[A-Za-zÀ-ÿ]", said):
            continue
        out.append((said, max((PAUSES.get(c, 0.0) for c in mark), default=0.12)))
    if out:
        out[-1] = (out[-1][0], 0.0)  # the speaker adds the silence between sentences
    return out
