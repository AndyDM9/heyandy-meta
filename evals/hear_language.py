"""Does Andy notice the language it's called in? The voice loop's second listening (voice/loop.py, _which_language),
on this computer's own models, with Andy in English.

For each of Andy's fourteen other languages, three everyday requests from evals/languages.py, said by Andy's own voice
in that language (SeamlessM4T v2, standing in for a person) after Andy's name as that language writes it ("安迪",
"Энди", "Andy"). The loop hears it as Andy does: Omnilingual ASR told English first; then, if it was called and didn't
understand, again told nothing. Scored: whether Andy switched, to which language, and whether the words heard again in
that language reach the right ability once Glimmer translates them. Then English: eight requests and four bits of
conversation, which must never switch it. Only the sentences, what was heard and the codes are kept.

    uv run python -m evals.hear_language          # about 3 minutes
"""
import json
import time
from pathlib import Path

from evals.languages import REQUESTS, WANT, right
from heyandy_meta.companion.language import LANGUAGES, Translator
from heyandy_meta.voice.local import LocalVoice
from heyandy_meta.voice.loop import VoiceLoop

NAME = {"zh": "安迪", "ko": "앤디", "ru": "Энди", "uk": "Енді", "ar": "آندي", "hi": "एंडी"}  # else "Andy"
SPANISH = ["¿Dónde están mis gafas?", "¿Has visto mis llaves?", "No encuentro mi teléfono"]
ENGLISH = ["Where are my glasses?", "Have you seen my keys?", "I can't find my phone", "Remind me at 5 pm to call my daughter",
           "Keep an eye on my wallet", "I'm going out, do I have everything?", "What time is it?", "Find the remote"]
CHAT = ["How are you today?", "Tell me something nice", "Thank you so much", "What a lovely morning"]


class Recording:
    """The ears, keeping what they wrote when told no language (the second listening), for the results."""

    def __init__(self, ears):
        self.ears, self.untold = ears, None

    @property
    def language(self):
        return self.ears.language

    @language.setter
    def language(self, value):
        self.ears.language = value

    def transcribe(self, samples, rate=16000, language=None):
        out = self.ears.transcribe(samples, rate, language)
        if language == "auto":
            self.untold = out
        return out


class Andy:
    """Just enough of Andy for the loop: its language and the switch."""

    def __init__(self):
        self.language, self.switched = "en", []

    @property
    def asr_language(self):
        return LANGUAGES[self.language].asr

    def notice_language(self, to):
        self.switched.append(to)
        self.language = to


def one(code: str, said: str, want, ears: LocalVoice, translator: Translator) -> dict:
    lang = LANGUAGES[code]
    line = NAME.get(code, "Andy") + ("，" if code == "zh" else ", ") + said
    audio = LocalVoice(voice=lang.voice, timeout=30).speak(line)
    andy = Andy()
    loop = VoiceLoop(andy)
    ears.language = "eng_Latn"
    first = ears.transcribe(audio)
    t = time.monotonic()
    rec = Recording(ears)
    text = loop._which_language(first, audio, rec)
    took = time.monotonic() - t
    to = andy.language
    english = translator.to_english(text, to) if to != "en" else text
    return {"language": code, "said": line, "heard as English": first, "heard told nothing": rec.untold, "switched to": andy.switched[-1] if andy.switched else None,
            "heard again": text if andy.switched else None, "english": english if andy.switched else None,
            "right language": to == code, "right ability": bool(andy.switched) and to == code and right(english, want),
            "seconds": round(took, 2)}


def main() -> None:
    ears, translator, rows = LocalVoice(timeout=30), Translator(), []
    for code in ["es", *REQUESTS]:
        said = SPANISH if code == "es" else REQUESTS[code][:3]
        for s, want in zip(said, WANT[:3]):
            r = one(code, s, want, ears, translator)
            rows.append(r)
            print(f"{code} {'ok ' if r['right ability'] else 'lang' if r['right language'] else '-- '} {r['said']!r} -> "
                  f"{r['switched to']} {r['heard again']!r} -> {r['english']!r}", flush=True)
    english = []
    for s in ENGLISH + CHAT:
        audio = LocalVoice(voice="eng", timeout=30).speak("Andy, " + s)
        andy, loop = Andy(), None
        loop = VoiceLoop(andy)
        ears.language = "eng_Latn"
        first = ears.transcribe(audio)
        loop._which_language(first, audio, ears)
        english.append({"said": "Andy, " + s, "heard": first, "switched to": andy.switched[-1] if andy.switched else None})
        print(f"en  {'SWITCHED' if andy.switched else 'stayed  '} {first!r}", flush=True)
    by = {}
    for r in rows:
        b = by.setdefault(r["language"], {"said": 0, "right language": 0, "right ability": 0, "wrong language": 0})
        b["said"] += 1
        b["right language"] += r["right language"]
        b["right ability"] += r["right ability"]
        b["wrong language"] += r["switched to"] is not None and not r["right language"]
    summary = {"requests in other languages": len(rows), "switched to the right language": sum(r["right language"] for r in rows),
               "and reached the right ability": sum(r["right ability"] for r in rows),
               "switched to a wrong language": sum(b["wrong language"] for b in by.values()),
               "english said": len(english), "english switched (must be 0)": sum(e["switched to"] is not None for e in english),
               "by language": {c: f"{b['right ability']}/{b['said']}" for c, b in by.items()}}
    out = Path("evals/results") / f"hear-language-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "requests": rows,
                               "english": english}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
