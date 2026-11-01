"""The languages scorecard: Andy in thirteen more languages, on this computer's own models.

For each language (companion/languages.py), eight everyday requests, written by hand for this test (not used to tune
anything), go through what Andy does in that language: Muse Glimmer translates them into English, and the request
rules sort them. Then the same requests spoken, by Andy's own voice in that language (SeamlessM4T v2, standing in for
a person) and heard by Omnilingual ASR told the language, so the hearing's slips count too. Then Andy's side: three of
its answers translated, spoken and heard back, scored by how much of their wording survives (the share of letters in
order, 1 is word for word). Nothing leaves this computer; only the sentences, the English and the timings are kept.

    uv run python -m evals.languages                   # every language, about 9 minutes (paced)
    uv run python -m evals.languages ru zh             # some
"""
import argparse
import json
import re
import statistics
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.language import LANGUAGES, PHRASES, Translator, asked_for
from heyandy_meta.companion.languages import MORE
from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE

# what each should reach: (ability, the thing)
WANT = [("find", "glasses"), ("find", "keys"), ("find", "phone"), ("remind", ""), ("watch", "wallet"),
        ("going_out", ""), ("time", ""), ("language", "")]
# "Where are my glasses?", "Have you seen my keys?", "I can't find my phone", "Remind me at 5 pm to call my
# daughter", "Keep an eye on my wallet", "I'm going out, do I have everything?", "What time is it?", "Speak English"
REQUESTS = {
    "zh": ["我的眼镜在哪里？", "你看到我的钥匙了吗？", "我找不到我的手机", "下午五点提醒我给女儿打电话", "帮我看着我的钱包",
           "我要出门了，东西都带齐了吗？", "现在几点了？", "说英语"],
    "tl": ["Nasaan ang salamin ko?", "Nakita mo ba ang mga susi ko?", "Hindi ko mahanap ang cellphone ko",
           "Paalalahanan mo ako mamayang alas singko ng hapon na tawagan ang anak ko", "Bantayan mo ang pitaka ko",
           "Aalis na ako, kumpleto na ba ang dala ko?", "Anong oras na?", "Mag-Ingles ka"],
    "vi": ["Kính của tôi đâu rồi?", "Bạn có thấy chìa khóa của tôi không?", "Tôi không tìm thấy điện thoại",
           "Nhắc tôi lúc năm giờ chiều gọi cho con gái", "Trông chừng cái ví của tôi",
           "Tôi đi ra ngoài đây, tôi có mang đủ đồ chưa?", "Mấy giờ rồi?", "Nói tiếng Anh đi"],
    "ko": ["내 안경 어디 있어?", "내 열쇠 봤어?", "휴대폰을 못 찾겠어", "오후 다섯 시에 딸에게 전화하라고 알려줘",
           "내 지갑 좀 지켜봐 줘", "나 나갈게, 다 챙겼나?", "지금 몇 시야?", "영어로 말해 줘"],
    "ru": ["Где мои очки?", "Ты не видел мои ключи?", "Не могу найти телефон", "Напомни мне в пять вечера позвонить дочери",
           "Присмотри за моим кошельком", "Я ухожу, я всё взял?", "Который час?", "Говори по-английски"],
    "ar": ["أين نظارتي؟", "هل رأيت مفاتيحي؟", "لا أجد هاتفي", "ذكرني في الساعة الخامسة مساءً أن أتصل بابنتي",
           "راقب محفظتي", "أنا خارج، هل معي كل شيء؟", "كم الساعة الآن؟", "تكلم بالإنجليزية"],
    "hi": ["मेरा चश्मा कहाँ है?", "क्या तुमने मेरी चाबियाँ देखीं?", "मुझे मेरा फ़ोन नहीं मिल रहा",
           "मुझे शाम पाँच बजे बेटी को फ़ोन करने की याद दिलाना", "मेरे बटुए पर नज़र रखना",
           "मैं बाहर जा रहा हूँ, क्या मेरे पास सब कुछ है?", "कितने बजे हैं?", "अंग्रेज़ी में बोलो"],
    "pt": ["Onde estão meus óculos?", "Você viu minhas chaves?", "Não acho meu celular",
           "Me lembra às cinco da tarde de ligar para minha filha", "Fica de olho na minha carteira",
           "Vou sair, estou levando tudo?", "Que horas são?", "Fala em inglês"],
    "fr": ["Où sont mes lunettes ?", "Tu as vu mes clés ?", "Je ne trouve pas mon téléphone",
           "Rappelle-moi à cinq heures de l'après-midi d'appeler ma fille", "Surveille mon portefeuille",
           "Je sors, est-ce que j'ai tout ?", "Quelle heure est-il ?", "Parle anglais"],
    "it": ["Dove sono i miei occhiali?", "Hai visto le mie chiavi?", "Non trovo il telefono",
           "Ricordami alle cinque del pomeriggio di chiamare mia figlia", "Tieni d'occhio il mio portafoglio",
           "Esco, ho preso tutto?", "Che ore sono?", "Parla inglese"],
    "pl": ["Gdzie są moje okulary?", "Widziałeś moje klucze?", "Nie mogę znaleźć telefonu",
           "Przypomnij mi o piątej po południu, żeby zadzwonić do córki", "Pilnuj mojego portfela",
           "Wychodzę, czy mam wszystko?", "Która godzina?", "Mów po angielsku"],
    "de": ["Wo ist meine Brille?", "Hast du meine Schlüssel gesehen?", "Ich finde mein Handy nicht",
           "Erinnere mich um fünf Uhr nachmittags daran, meine Tochter anzurufen", "Behalte meine Geldbörse im Auge",
           "Ich gehe raus, habe ich alles?", "Wie spät ist es?", "Sprich Englisch"],
    "uk": ["Де мої окуляри?", "Ти бачив мої ключі?", "Не можу знайти телефон", "Нагадай мені о п'ятій вечора зателефонувати доньці",
           "Наглядай за моїм гаманцем", "Я йду, чи я все взяв?", "Котра година?", "Говори англійською"],
}
# Andy's side: an answer with its find opener (by hand) and the rest (translated), and two more
ANSWERS = ["There they are! On the table, to my left, about 1.5 meters away.",
           "I'll remind you at 5 PM to call your daughter.", "I'm keeping an eye on your wallet."]
assert set(REQUESTS) == set(MORE) and all(len(r) == len(WANT) for r in REQUESTS.values())


def reached(english: str) -> tuple[str, str]:
    if asked_for(english) == "en":
        return "language", ""
    i = parse(english)
    return i.kind, i.thing or ""


def right(english: str, want: tuple[str, str]) -> bool:
    kind, thing = reached(english)
    return kind == want[0] and (not want[1] or want[1] in thing or (want[1] == "phone" and "phone" in thing))


def letters(text: str) -> str:
    return re.sub(r"[\W\d_]+", "", unicodedata.normalize("NFC", text)).casefold()


def heard_back(said: str, heard: str) -> float:
    return SequenceMatcher(None, letters(said), letters(heard)).ratio()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="*", help="language codes (default: all)")
    ap.add_argument("--out", default="evals/results")
    ap.add_argument("--pause", type=float, default=20.0, help="seconds between languages, so the GPUs rest")
    args = ap.parse_args()

    translator, rows = Translator(), {}
    out = Path(args.out) / f"languages-{time.strftime('%Y%m%d-%H%M')}.json"
    for k, code in enumerate(args.langs or REQUESTS):
        if k:
            time.sleep(args.pause)  # paced: GPU 0 fell off the bus 3 minutes into running these back to back (Oct 31)
        try:
            rows[code] = one(code, translator)
        except Exception as e:  # noqa: BLE001 - a language that fails is a line in the results, not the end of them
            rows[code] = {"name": LANGUAGES[code].name, "error": f"{type(e).__name__}: {e}"[:300]}
            print(f"{code} failed: {rows[code]['error']}", flush=True)
        save(out, rows)
    print(f"saved {out}")


def save(out: Path, rows: dict) -> None:
    done = [r for r in rows.values() if "error" not in r]
    summary = {"languages": len(done), "failed": [c for c, r in rows.items() if "error" in r], "requests": len(done) * len(WANT),
               "written right": sum(r["written_right"] for r in done), "spoken right": sum(r["spoken_right"] for r in done)}
    if done:
        summary["Andy heard back, median"] = statistics.median(r["heard_back"] for r in done)
        summary["translation into English, median s"] = statistics.median(x["seconds"] for r in done for x in r["written"])
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "languages": rows},
                              indent=1, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def one(code: str, translator) -> dict:
    from heyandy_meta.voice.local import LocalVoice

    lang = LANGUAGES[code]
    translator.failures = 0
    mouth, ears = LocalVoice(voice=lang.voice), LocalVoice()
    ears.language = lang.asr
    r = {"name": lang.name, "written": [], "spoken": [], "answers": []}
    for said, want in zip(REQUESTS[code], WANT):
        t = time.monotonic()
        english = translator.to_english(said, code)
        r["written"].append({"said": said, "english": english, "reached": reached(english), "right": right(english, want),
                             "seconds": round(time.monotonic() - t, 2)})
        audio = mouth.speak(said)
        heard = ears.transcribe(audio)
        english = translator.to_english(heard, code)
        r["spoken"].append({"heard": heard, "english": english, "reached": reached(english), "right": right(english, want)})
    for answer in ANSWERS:
        t = time.monotonic()
        spoken = translator.spoken(answer, code, DISCLOSURE, CRISIS_REPLY)
        took = time.monotonic() - t
        heard = ears.transcribe(mouth.speak(spoken))
        r["answers"].append({"english": answer, "said": spoken, "heard": heard, "heard_back": round(heard_back(spoken, heard), 2),
                             "translated_s": round(took, 2), "by_hand": answer.split("!")[0] + "!" in PHRASES[code]})
    if translator.failures:
        raise RuntimeError("Glimmer stopped answering")  # the words would go through untranslated: not a result
    r["written_right"] = sum(x["right"] for x in r["written"])
    r["spoken_right"] = sum(x["right"] for x in r["spoken"])
    r["heard_back"] = round(statistics.mean(x["heard_back"] for x in r["answers"]), 2)
    print(f"{code} {lang.name:11} written {r['written_right']}/{len(WANT)}  spoken {r['spoken_right']}/{len(WANT)}  "
          f"Andy heard back {r['heard_back']:.2f}", flush=True)
    for x, y in zip(r["written"], r["spoken"]):
        if not (x["right"] and y["right"]):
            print(f"    {x['said']} -> {x['english']!r} {x['reached']} | heard {y['heard']!r} -> {y['english']!r} {y['reached']}")
    return r


if __name__ == "__main__":
    main()
