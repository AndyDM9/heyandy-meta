"""Andy's own voice for the public demo's front door: the line it says before its first answer on the robot ("I'm
Andy, an AI robot."), in each of its fifteen languages, made by its voice service (Meta's SeamlessM4T v2 on this
computer, local/voice_server.py) exactly as the robot says it, and kept as small MP3s with the page.

The words are Andy's hand-written ones (companion/language.py and companion/safety.py DISCLOSURE): nothing is
translated for the page. A manifest beside them keeps each clip's words, voice, length and SHA-256, so a test knows
each sounds like what the page shows. Made once, here (the voice service runs on the robot's computer); the Space's
build copies them.

    uv run python scripts/front_door_voice.py        # -> heyandy_meta/screen/voice/: <language>.mp3, voice.json,
                                                     #    the story's chapters, story-NN.mp3 and story.json,
                                                     #    find mode's words, find-<language>-<moment>.mp3,
                                                     #    and each demo scene's line, scene-<name>.mp3; then
                                                     #    the story in its other languages (below)
    uv run python scripts/front_door_voice.py --story-in ko ar   # only the story, in these (or, with none, all 14)
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "heyandy_meta" / "screen" / "voice"
RATE = 16000  # what the robot's speaker is sent


def lines() -> dict[str, tuple[str, str, str]]:
    """{language: (Andy's hand-written introduction, its SeamlessM4T voice, its Omnilingual ASR language)}"""
    from heyandy_meta.companion.language import LANGUAGES
    from heyandy_meta.companion.safety import DISCLOSURE

    return {code: (lang.disclosure or DISCLOSURE, lang.voice, lang.asr) for code, lang in LANGUAGES.items()}


# The story (page.html STORY), told by Andy in its own voice: each chapter's line in the first person, saying no more than
# the line and its proof under it (a chapter not yet tried on the robot says so on screen, as before). By chapter title.
STORY = {
    "Andy, on the table": "This is me, on the table. I turn to your voice, look around the room, and point.",
    "Meet Andy": "Hi, I'm Andy. I find what you've lost, and point at it. This is the TV beside me.",
    "You ask": "You ask: Hey Andy, where's my mug? I look around the room, and SAM 3.1 outlines everything that could be it.",
    "It finds it": "There it is. I point, check my aim with my own camera, and MapAnything tells me how far away it is.",
    "It doesn't give up": "Not found? I keep looking while you get on with your day, and tell you the moment it turns up.",
    "It guides your hand": "Can't see well? I watch your hand and talk it onto the thing, from your side: toward you, and right.",
    "It knows your room": "Five looks, and I know your room in 3D, your things pinned. Its shape only, never a picture.",
    "Identical cups, told apart": "Identical cups? SAM 3.1 Object Multiplex follows every one of them through the shuffle.",
    "Before you go": "Going out? I point at what you'd leave behind, and Muse Spark checks whether you'll need an umbrella.",
    "Your language": "I hear and speak fifteen languages. Muse Glimmer translates, on the computer beside me.",
    "What it never does": "And what I never do: your pictures and voice stay home, I give no health advice, and I say I'm an AI.",
    "Your turn": "That's me. Now it's your turn: show me something of yours.",  # the end card, after the last chapter
}


# Andy's eyes, find mode (eyes.html): what the robot says at the same moments, by hand in each language
# (companion/language.py PHRASES): the shutter, the sweep starting, and the find (one thing, or a pair: keys, glasses).
FIND = {"see": "Let me see.", "look": "Let me look around the room.", "it": "There it is!", "they": "There they are!"}


def find_lines() -> dict[str, dict[str, str]]:
    """{language: {moment: Andy's hand-written words}}: only where every moment has its words."""
    from heyandy_meta.companion.language import LANGUAGES, PHRASES

    out = {}
    for code in LANGUAGES:
        words = {k: (v if code == "en" else PHRASES.get(code, {}).get(v)) for k, v in FIND.items()}
        if all(words.values()):
            out[code] = words
    return out


def scene_lines() -> dict[str, tuple[str, str]]:
    """{scene: (what Andy says in it, its language)}: the public demo's scenes as the Space's build makes them
    (scripts/demo_screen.py), each one's caption, the words the TV shows Andy saying."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from demo_screen import IN_LANGUAGE, SCENES, show

    from heyandy_meta.screen.state import ScreenState

    out = {}
    for name in (*SCENES, *IN_LANGUAGE):
        state = ScreenState()
        show(state, name)
        snap = state.snapshot()
        text = (snap.get("caption") or "").strip()
        if text:
            out[name] = (text, snap.get("lang") or "en")
    return out


# The story in Andy's other fourteen languages, for a visitor who reads and hears one (page.html: the welcome's globe, or
# the browser's own language): each chapter's line and title translated by Muse Glimmer on this computer, the model
# Andy translates its own words with, told the story's names; said by SeamlessM4T v2 in the language's voice, heard back
# by Omnilingual ASR, and translated back into English by Glimmer, kept beside it so anyone can read what it says.
# Machine-checked, not yet by a native speaker of each: a language is offered only when every chapter passes.
# November 2: Andy's own sentence-by-sentence path, made for its short replies, looped a Korean line into "hello" 35
# times, left "Identical cups?" in English and wrote Muse Glimmer in Arabic letters, so the story has its own prompt.
NAMES = ("SAM 3.1 Object Multiplex", "SAM 3.1", "MapAnything", "Muse Spark", "Muse Glimmer")  # Andy: any script
TELL = ("You translate one line of a short story that a small home robot named Andy tells about itself, out loud, into "
        "{name}: natural, warm, spoken {name}, polite to the listener, as to an older person you respect (Spanish "
        "'usted', French 'vous', German 'Sie', Russian and Ukrainian 'вы', Chinese '您'). 'I', 'me' and 'my' are the "
        "robot; 'you' is the listener. A short question in the line (\"Not found?\", \"Identical cups?\") is the robot "
        "asking the listener, and is translated too ('identical' cups look exactly alike). Words after \"You ask:\" "
        "are what a person says to the robot: translate them as that person would say them to it. Keep these names exactly as written, in Latin letters, "
        "never translated or written in another script: " + ", ".join(NAMES) + ". Translate every other word. Never "
        "add anything, never answer or greet: only the {name} translation of the text between <<< and >>>.")
TITLE = ("You translate the title of one chapter of a short story about a small home robot named Andy into {name}: a "
         "few natural words of {name}, as a heading. Keep the name Andy. Translate every word; only the {name} title, "
         "for the text between <<< and >>>.")
# For the translator only, where the story's English trips it (a line the story says, translated from plainer words):
# "Identical cups?" and "the shuffle" came back in English in Spanish three times, by every way of asking.
PLAINER = {"Identical cups, told apart": "Cups that look exactly alike? SAM 3.1 Object Multiplex follows every one of "
                                         "them while they're shuffled."}
OTHER = ("Say this line a small home robot speaks, in {name}, in other words: everyday spoken {name}, the same meaning, "
         "nothing added or left out, polite to the listener. Keep these names exactly as written, in Latin letters: "
         + ", ".join(NAMES) + ". Only the new {name} line, for the text between <<< and >>>.")
SIMPLER = ("Say this line a small home robot speaks, in {name}, again more simply: short everyday spoken {name}, the same "
           "meaning, nothing added or left out, polite to the listener. Keep these names exactly as written, in Latin "
           "letters: " + ", ".join(NAMES) + ". Only the new {name} line, for the text between <<< and >>>.")
BACK = ("You translate one line of a short story that a small home robot tells about itself, out loud, from {name} into "
        "English, as close to its meaning as you can. 'I', 'me' and 'my' are the robot. Never add anything, never answer "
        "it, never write it in {name}: only the English translation of the text between <<< and >>>.")
SAID = re.compile(r"(?<=[。！？؟।])\s*|(?<=[.!?])\s+")  # sentences, in any of the fifteen scripts ("3.1" stays whole)


def tokens(text: str) -> list[str]:
    """Words split at spaces, punctuation and symbols dropped (a Devanagari vowel sign is part of its word; Python's
    \\w splits there, and Hindi's first check found "a word over and over" in every line)."""
    import unicodedata

    out = ["".join(ch for ch in w if not unicodedata.category(ch).startswith(("P", "S"))) for w in text.split()]
    return [w.casefold() for w in out if any(ch.isalpha() for ch in w)]


def problems(english: str, out: str, latin: bool = True) -> list[str]:
    """What's wrong with a translation of one of the story's lines, by machine: a name lost or written in another
    script, English left in it (in a language written in other letters, one English word is too many; in Latin letters,
    one may be its own word too, German "Hand"), a word repeated over and over (a loop), far too long, or a figure the
    English hasn't."""
    wrong = [f"lost {n}" for n in NAMES if n in english and n not in out]
    if "SAM 3.1 Object Multiplex" in out:
        wrong = [w for w in wrong if w != "lost SAM 3.1"]
    rest = re.sub(r"\bHey Andy\b", " ", out)  # the words that wake Andy, in any language
    for n in (*NAMES, "Andy"):
        rest = rest.replace(n, " ")
    words = tokens(rest)
    english_words = {w for w in tokens(english) if len(w) >= 3 and w.isascii()}
    left = [w for w in words if w in english_words]
    if len(left) > (1 if latin else 0):
        wrong.append("English left: " + " ".join(left))
    if (words and max(words.count(w) for w in set(words)) > 4) or re.search(r"(.{2,}?)\1{4,}", out):
        wrong.append("a word over and over")
    if len(out) > 3 * len(english):
        wrong.append("too long")
    if set(re.findall(r"\d+", out)) - set(re.findall(r"\d+", english)):
        wrong.append("a figure the English hasn't")
    return wrong


def glimmer(system: str, text: str) -> str:
    from heyandy_meta.models import glimmer_fast

    messages = [{"role": "system", "content": system}, {"role": "user", "content": f"<<<{text}>>>"}]
    out = glimmer_fast.answer("http://127.0.0.1:8080", messages, 3 * len(text) + 20, stop=[">>>", "\n\n"], timeout=60)
    return out.replace("<<<", "").strip().strip('"').strip()


def named(out: str, code: str) -> str:
    """A name Glimmer wrote as it sounds, in the language's letters, written as the name again (November 2, Arabic:
    "ميوز غليمر" for Muse Glimmer, the very spelling its voice is given), so the words on screen keep it."""
    sounds = SOUNDS.get(code, {})
    for name, said in sorted(sounds.items(), key=lambda x: -len(x[1])):
        out = out.replace(said, name)
    full, short = sounds.get("SAM 3.1 Object Multiplex", ""), sounds.get("SAM 3.1", "")
    if full.startswith(short + " "):  # Hindi: "SAM 3.1 ऑब्जेक्ट मल्टीप्लेक्स", its last two words by their sound
        out = out.replace(full[len(short) + 1:], "Object Multiplex")
    return out


def translated(text: str, code: str, title: bool = False) -> tuple[str, str]:
    """(the line in the language, how): the whole line at once; else sentence by sentence (a short question first,
    "Identical cups?", came back in English); else as Andy translates its own words on the robot. The last try is kept,
    with its problems, when none passes: the caller doesn't offer the language. A chapter's title has its own words."""
    from heyandy_meta.companion.language import LANGUAGES, Translator
    from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE

    system, latin = (TITLE if title else TELL).format(name=LANGUAGES[code].name), LANGUAGES[code].asr.endswith("_Latn")
    out = named(glimmer(system, text), code)
    if not problems(text, out, latin):
        return out, "whole line"
    parts = [x for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    if len(parts) > 1:
        out = named(" ".join(glimmer(system, x) for x in parts), code)
        if not problems(text, out, latin):
            return out, "sentence by sentence"
    return named(Translator(timeout=60).spoken(text, code, DISCLOSURE, CRISIS_REPLY), code), "as on the robot"


# How each name sounds, by hand, in the languages written in other letters, for their voices: a Korean voice reads a
# Latin name badly (November 2: "SAM 3.1 Object Multiplex" heard back as "트리포 1 업트 몰티플렉스"), and Glimmer's
# own spellings were worse ("SAM 3.1" as "세이엠 쓰리 원", "Muse Spark" with a "3"). The words on screen keep the names
# as written. Mandarin's voice reads most of them well as written (Chinese writes them in Latin letters), not MapAnything:
# "马派你..." (heard back at 0.62 in its line), and "迈普艾尼辛", its sound, at 0.87.
SOUNDS = {
    "zh": {"MapAnything": "迈普艾尼辛"},
    "ko": {"SAM 3.1 Object Multiplex": "샘 쓰리 포인트 원 오브젝트 멀티플렉스", "SAM 3.1": "샘 쓰리 포인트 원",
           "MapAnything": "맵 애니씽", "Muse Spark": "뮤즈 스파크", "Muse Glimmer": "뮤즈 글리머"},
    "ar": {"SAM 3.1 Object Multiplex": "سام ثلاثة فاصلة واحد أوبجكت ملتيبلكس", "SAM 3.1": "سام ثلاثة فاصلة واحد",
           "MapAnything": "ماب إني ثينغ", "Muse Spark": "ميوز سبارك", "Muse Glimmer": "ميوز غليمر"},
    "hi": {"SAM 3.1 Object Multiplex": "सैम थ्री पॉइंट वन ऑब्जेक्ट मल्टीप्लेक्स", "SAM 3.1": "सैम थ्री पॉइंट वन",
           "MapAnything": "मैप एनीथिंग", "Muse Spark": "म्यूज़ स्पार्क", "Muse Glimmer": "म्यूज़ ग्लिमर"},
    "ru": {"SAM 3.1 Object Multiplex": "Сэм три точка один Обджект Мультиплекс", "SAM 3.1": "Сэм три точка один",
           "MapAnything": "Мэп Энисинг", "Muse Spark": "Мьюз Спарк", "Muse Glimmer": "Мьюз Глиммер"},
    "uk": {"SAM 3.1 Object Multiplex": "Сем три крапка один Обджект Мультиплекс", "SAM 3.1": "Сем три крапка один",
           "MapAnything": "Меп Енісінг", "Muse Spark": "М'юз Спарк", "Muse Glimmer": "М'юз Гліммер"},
}


def aloud(text: str, said_as: dict[str, str]) -> str:
    """The line as the voice is given it: each name as it sounds (the longest first: SAM 3.1 Object Multiplex)."""
    for name in sorted(said_as, key=len, reverse=True):
        text = text.replace(name, said_as[name])
    return text


def rephrased(how: str, text: str, source: str, code: str) -> str:
    """The same line again, for a voice that stumbled on it: Glimmer asked to say it more simply, or in other words; or
    the English translated as Andy translates its own words on the robot, or sentence by sentence."""
    from heyandy_meta.companion.language import LANGUAGES, Translator
    from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE

    name = LANGUAGES[code].name
    if how == "said more simply":
        return glimmer(SIMPLER.format(name=name), text)
    if how == "said in other words":
        return glimmer(OTHER.format(name=name), text)
    if how == "as on the robot":
        return Translator(timeout=60).spoken(source, code, DISCLOSURE, CRISIS_REPLY)
    return " ".join(glimmer(TELL.format(name=name), x) for x in re.split(r"(?<=[.!?])\s+", source) if x.strip())


def story_in(codes=None, pause: float = 20.0) -> None:
    """The story (STORY) in each of Andy's other languages, or these: story-<language>-NN.mp3 and story-in.json, which
    keeps each chapter's words, how they were translated, their translation back, how they were heard back, and why a
    language isn't offered (the page offers only the rest). A language made again replaces only its own entry."""
    import time

    import numpy as np

    from difflib import SequenceMatcher

    from evals.languages import heard_back
    from heyandy_meta.companion.language import LANGUAGES, Translator
    from heyandy_meta.voice.local import LocalVoice

    path = OUT / "story-in.json"
    kept = json.loads(path.read_text())["languages"] if path.exists() else {}
    for k, code in enumerate(codes or [c for c in LANGUAGES if c != "en"]):
        if k:
            time.sleep(pause)  # paced: Glimmer and the voice share GPU 0, which fell off the bus under a long run (Oct 31)
        lang, chapters, wrong = LANGUAGES[code], {}, []
        speaker, said_as = LocalVoice("http://127.0.0.1:8092", voice=lang.voice), SOUNDS.get(code, {})
        latin = lang.asr.endswith("_Latn")
        def voiced(text: str, n: int, code=code, lang=lang, speaker=speaker, said_as=said_as) -> tuple[str, float, float]:
            """Said sentence by sentence, as the robot's speaker makes them, and heard back the same way, weighted by
            length: (the words the voice was given, the clip's seconds, how well they were heard back)."""
            spoken = aloud(text, said_as)
            sentences = [x for x in SAID.split(spoken.strip()) if x.strip()]
            parts = [speaker.speak(x, rate=RATE) for x in sentences]
            gap = np.zeros(int(0.12 * RATE), np.float32)
            seconds = mp3(np.concatenate([y for part in parts for y in (part, gap)][:-1]), OUT / f"story-{code}-{n:02d}.mp3")
            scores = [heard_back(x, speaker.transcribe(a, RATE, language=lang.asr)) for x, a in zip(sentences, parts)]
            return spoken, seconds, round(sum(sc * len(a) for sc, a in zip(scores, parts)) / sum(len(a) for a in parts), 2)

        def wrong_with(english: str, out: str, source: str, latin=latin) -> list[str]:
            return sorted(set(problems(english, out, latin)) | set(problems(source, out, latin)))

        for n, (title, english) in enumerate(STORY.items()):
            source = PLAINER.get(title, english)
            text, how = translated(source, code)
            if source != english:
                how += ", from plainer English"
            name, _ = translated(title, code, title=True) if title != "Your turn" else ("", "")  # the end card has none
            spoken, seconds, heard = voiced(text, n)
            if heard < HEARD and not wrong_with(english, text, source):
                # the voice is the same every time (Mandarin's "十五种语言" heard as "初始无种预言", three times in three),
                # and the same meaning in other words can come out clearly: more simply, else in other words, each kept
                # only if it passes every check
                for said_how in ("said more simply", "said in other words", "as on the robot", "sentence by sentence"):
                    other = named(rephrased(said_how, text, source, code), code)
                    if other == text:  # Mandarin: handed back unchanged, twice
                        continue
                    if wrong_with(english, other, source):
                        print(f"   {said_how}, not kept: {wrong_with(english, other, source)}  {other}", flush=True)
                        continue
                    again = voiced(other, n)
                    if again[2] >= HEARD:
                        text, how, (spoken, seconds, heard) = other, f"{how}, {said_how}", again
                        break
                    print(f"   {said_how}, not kept: heard back {again[2]:.2f}  {other}", flush=True)
                else:
                    voiced(text, n)  # the clip of the words kept
            back = glimmer(BACK.format(name=lang.name), text)
            if SequenceMatcher(None, back.casefold(), text.casefold()).ratio() > 0.5:  # French came back in French
                back = Translator(timeout=60).to_english(text, code)
            found = wrong_with(english, text, source) + [f"title: {p}" for p in (problems(title, name, latin) if name else [])]
            if heard < HEARD:
                found.append(f"heard back {heard:.2f}")
            wrong += [f"{title}: {p}" for p in found]
            clip = OUT / f"story-{code}-{n:02d}.mp3"
            chapters[title] = {"title": name, "text": text, "how": how, "back": back, "said": spoken, "seconds": seconds,
                               "file": f"voice/{clip.name}", "heard back": heard,
                               "sha256": hashlib.sha256(clip.read_bytes()).hexdigest()}
            print(f"{code} {n:02d} {how:22} heard {heard:.2f} {found or ''}  {text}", flush=True)
        kept[code] = {"offered": not wrong, "why not": wrong, "names said as": said_as, "chapters": chapters}
        print(f"== {code}: {'offered' if not wrong else 'not offered: ' + '; '.join(wrong)}", flush=True)
        path.write_text(json.dumps({"what": "The story in Andy's other languages: translated by Muse Glimmer, said by "
                                            "SeamlessM4T v2, heard back by Omnilingual ASR, translated back by Glimmer",
                                    "checked by a native speaker": [], "languages": dict(sorted(kept.items()))},
                                   ensure_ascii=False, indent=1))


HEARD = 0.75  # a chapter heard back at least this well (a Latin-letter name in another script's voice is heard as its sound)


def mp3(samples, path: Path) -> float:
    """Mono float samples at RATE, as a small MP3; returns the seconds."""
    import numpy as np

    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "24000",
                        "-c:a", "libmp3lame", "-b:a", "40k", str(path)], check=True)
    return round(len(samples) / RATE, 2)


def main() -> None:
    from heyandy_meta.voice.local import LocalVoice

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    from evals.languages import heard_back

    for code, (text, voice, asr) in lines().items():
        speaker = LocalVoice("http://127.0.0.1:8092", voice=voice)
        samples = speaker.speak(text, rate=RATE)
        path = OUT / f"{code}.mp3"
        seconds = mp3(samples, path)
        # heard back by Andy's own ears (Omnilingual ASR, told the language): the clip says its words
        heard = round(heard_back(text, speaker.transcribe(samples, RATE, language=asr)), 2)
        manifest[code] = {"text": text, "voice": voice, "seconds": seconds, "file": f"voice/{code}.mp3",
                          "heard back": heard, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"{code}: {seconds:.2f} s, {path.stat().st_size // 1024} KB, heard back {heard:.2f}  {text}")
    (OUT / "voice.json").write_text(json.dumps({"what": __doc__.strip().splitlines()[0], "model": "SeamlessM4T v2",
                                                "clips": manifest}, ensure_ascii=False, indent=1))
    print(f"saved {len(manifest)} clips in {OUT}")
    told = {}
    speaker = LocalVoice("http://127.0.0.1:8092", voice="eng")
    for n, (title, text) in enumerate(STORY.items()):
        samples = speaker.speak(text, rate=RATE)
        path = OUT / f"story-{n:02d}.mp3"
        seconds = mp3(samples, path)
        heard = round(heard_back(text, speaker.transcribe(samples, RATE, language="eng_Latn")), 2)
        told[title] = {"text": text, "seconds": seconds, "file": f"voice/story-{n:02d}.mp3", "heard back": heard,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"story {n:02d}: {seconds:.2f} s, heard back {heard:.2f}  {title}")
    (OUT / "story.json").write_text(json.dumps({"what": "The story, told by Andy in its own voice (SeamlessM4T v2)",
                                                "chapters": told}, ensure_ascii=False, indent=1))
    from heyandy_meta.companion.language import LANGUAGES

    found = {}
    for code, words in find_lines().items():
        speaker = LocalVoice("http://127.0.0.1:8092", voice=LANGUAGES[code].voice)
        found[code] = {}
        for moment, text in words.items():
            samples = speaker.speak(text, rate=RATE)
            path = OUT / f"find-{code}-{moment}.mp3"
            seconds = mp3(samples, path)
            heard = round(heard_back(text, speaker.transcribe(samples, RATE, language=LANGUAGES[code].asr)), 2)
            found[code][moment] = {"text": text, "seconds": seconds, "file": f"voice/find-{code}-{moment}.mp3",
                                   "heard back": heard, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"find {code}: " + ", ".join(f"{m} {c['heard back']:.2f}" for m, c in found[code].items()))
    (OUT / "find.json").write_text(json.dumps({"what": "Andy's eyes, find mode, in Andy's own voice (SeamlessM4T v2)",
                                               "languages": found}, ensure_ascii=False, indent=1))
    import numpy as np

    from heyandy_meta.voice.speaker import SENTENCE

    spoken = {}
    for name, (text, lang) in scene_lines().items():
        speaker = LocalVoice("http://127.0.0.1:8092", voice=LANGUAGES[lang].voice)
        # sentence by sentence, as the robot's speaker makes them (voice/speaker.py): a long paragraph in one go comes out
        # worse (the keys' story, 17.8 s at once, was heard back at 0.56)
        sentences = [x for x in SENTENCE.split(text.strip()) if x.strip()]
        parts = [speaker.speak(x, rate=RATE) for x in sentences]
        gap = np.zeros(int(0.12 * RATE), np.float32)
        samples = np.concatenate([y for part in parts for y in (part, gap)][:-1])
        path = OUT / f"scene-{name}.mp3"
        seconds = mp3(samples, path)
        # heard back sentence by sentence (Omnilingual ASR hears an utterance of a few seconds, as Andy's ears cut them:
        # the keys' story heard whole, 18.8 s, scored 0.56, each of its sentences 0.74 to 1.00), weighted by length
        scores = [heard_back(x, speaker.transcribe(a, RATE, language=LANGUAGES[lang].asr)) for x, a in zip(sentences, parts)]
        heard = round(sum(sc * len(a) for sc, a in zip(scores, parts)) / sum(len(a) for a in parts), 2)
        spoken[name] = {"text": text, "lang": lang, "seconds": seconds, "file": f"voice/scene-{name}.mp3",
                        "heard back": heard, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"scene {name}: {lang} {seconds:.1f} s, heard back {heard:.2f}")
    (OUT / "scenes.json").write_text(json.dumps({"what": "The public demo's scenes, each said in Andy's own voice (SeamlessM4T v2)",
                                                 "scenes": spoken}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--story-in", nargs="*", metavar="LANGUAGE", help="only the story in Andy's other languages (all, or these)")
    args = ap.parse_args()
    if args.story_in is None:
        main()
    story_in(args.story_in or None)
