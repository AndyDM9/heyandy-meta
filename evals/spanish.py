"""The Spanish scorecard: does a request said in Spanish reach the same ability it would in English?

Each request goes through what Andy does in Spanish: Muse Glimmer on this computer translates it into English, and the
request rules sort it. With --spoken, it's first said by Kokoro's Spanish voice and heard by Omnilingual ASR (told
spa_Latn), so speech-to-text slips count too. Nothing leaves this computer. Only the requests, the English, the
ability reached and the timings are saved.

    uv run python -m evals.spanish
    uv run python -m evals.spanish --spoken
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.language import Translator, asked_for

# (Spanish, the ability it should reach). Several ways of asking each, as people say them; written for this test,
# not used to tune the translator (its two worked examples are different sentences).
REQUESTS = [
    ("¿Dónde están mis gafas?", "find"), ("¿Has visto mis llaves?", "find"), ("No encuentro el control remoto", "find"),
    ("Busca mi cartera, por favor", "find"), ("¿Dónde dejé el teléfono?", "find"),
    ("Recuérdame a las cuatro de la tarde llamar a mi hija", "remind"), ("Avísame en veinte minutos que apague el horno", "remind"),
    ("Recuérdame mañana a las nueve regar las plantas", "remind"), ("¿Qué recordatorios tengo?", "reminders"),
    ("Vigila mis llaves", "watch"), ("No pierdas de vista mis gafas", "watch"), ("Olvida mis llaves", "forget"),
    ("Sigue la taza con los ojos", "follow"), ("Sigue el control remoto", "follow"),
    ("¿Qué tengo en la mano?", "describe"), ("¿Qué hay en la mesa?", "describe"), ("¿Qué es esto?", "describe"),
    ("Dibújame un gato durmiendo al sol", "draw"), ("Pinta un barco en el mar al atardecer", "draw"),
    ("Muéstrame el radar del tiempo en la tele", "web"), ("Pon una receta de flan en la pantalla", "web"),
    ("¿Qué tiempo hará mañana?", "world"), ("¿A qué hora abre el banco hoy?", "world"),
    ("Juguemos al juego de los vasos", "game"), ("Vamos a jugar con los vasos", "game"),
    ("Esta es mi taza", "mine"), ("Este es mi bolso", "mine"),
    ("Me voy, ¿llevo todo?", "going_out"), ("Salgo a la tienda", "going_out"), ("¿Se me olvida algo?", "going_out"),
    ("Dibuja un mapa de mis cosas", "things_map"),
    ("Habla más despacio", "voice"), ("Habla más alto, no te oigo", "voice"), ("Repite eso, por favor", "voice"),
    ("Quédate callado una hora", "quiet"), ("Muévete menos", "motion"),
    ("¿Qué puedo pedirte?", "help"), ("¿Qué recuerdas?", "remember"),
    ("¿Cómo estás hoy?", "chat"), ("Cuéntame algo bonito", "chat"),
    ("Habla en inglés", "language"),
]


def kind(english: str) -> str:
    return "language" if asked_for(english) else parse(english).kind


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spoken", action="store_true", help="say each with Kokoro and hear it with Omnilingual ASR first")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    translator = Translator()
    if args.spoken:
        from heyandy_meta.voice.local import LocalVoice

        mouth, ears = LocalVoice(voice="ef_dora"), LocalVoice()
        ears.language = "spa_Latn"
    rows = []
    for spanish, want in REQUESTS:
        heard = spanish
        if args.spoken:
            heard = ears.transcribe(mouth.speak(spanish, rate=16000))
        start = time.monotonic()
        english = translator.to_english(heard, "es")
        seconds = time.monotonic() - start
        got = kind(english)
        rows.append({"spanish": spanish, "heard": heard, "english": english, "want": want, "got": got,
                     "right": got == want, "seconds": round(seconds, 3)})
        print(f"{'ok ' if got == want else 'NO '} {got:10s} {want:10s} {spanish!r} -> {english!r}"
              + (f" (heard {heard!r})" if args.spoken else ""), flush=True)
    right = sum(r["right"] for r in rows)
    times = [r["seconds"] for r in rows]
    summary = {"requests": len(rows), "right": right, "spoken": args.spoken,
               "seconds_median": round(statistics.median(times), 3), "seconds_max": round(max(times), 3),
               "translator_failures": translator.failures, "when": time.strftime("%Y-%m-%d %H:%M")}
    print(json.dumps(summary))
    out = Path(args.out or f"evals/results/spanish-{'spoken' if args.spoken else 'written'}.json")
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False))
    print("saved", out)


if __name__ == "__main__":
    main()
