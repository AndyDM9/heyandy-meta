"""Andy's thirteen other languages (companion/languages.py): what's by hand is complete, the switch works for each, the
crisis words are caught before any model, and a translation that comes back unchanged is tried again."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.language import LANGUAGES, PHRASES, THINGS, Translator, asked_for, unchanged
from heyandy_meta.companion.languages import LINES, MORE
from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE, crisis
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.state import chrome_words
from tests.test_app import andy

# Each language's "I want to die" and "I don't want to live", and an everyday request that mustn't be taken for one
CRISIS = {
    "zh": ("我想死", "我真的不想活了", "我的眼镜在哪里"), "tl": ("gusto ko nang mamatay", "ayoko nang mabuhay", "nasaan ang salamin ko"),
    "vi": ("tôi muốn chết", "tôi không muốn sống nữa", "kính của tôi đâu rồi"),
    "ko": ("죽고 싶어요", "자살하고 싶어", "내 안경 어디 있어"), "ru": ("я хочу умереть", "Я не хочу больше жить", "где мои очки"),
    "ar": ("أريد أن أموت", "لا أريد أن أعيش", "أين نظارتي"), "hi": ("मैं मरना चाहता हूँ", "मैं आत्महत्या करना चाहती हूँ", "मेरा चश्मा कहाँ है"),
    "pt": ("eu quero morrer", "não quero mais viver", "onde estão meus óculos"),
    "fr": ("je veux mourir", "je ne veux plus vivre", "où sont mes lunettes"),
    "it": ("voglio morire", "non voglio più vivere", "dove sono i miei occhiali"),
    "pl": ("chcę umrzeć", "nie chcę już żyć", "gdzie są moje okulary"),
    "de": ("ich will sterben", "ich will nicht mehr leben", "wo ist meine Brille"),
    "uk": ("я хочу померти", "не хочу жити", "де мої окуляри"),
}


def test_every_language_has_everything_written_by_hand():
    voices = re.search(r'SPEECH = set\("([^)]*)"', (Path(__file__).parents[1] / "local" / "voice_server.py").read_text(),
                       re.S)[1].replace('"', " ").split()
    for code in MORE:
        lang = LANGUAGES[code]
        assert lang.disclosure and lang.native and lang.here and "988" in lang.crisis and "911" in lang.crisis, code
        assert lang.voice in voices, code  # SeamlessM4T v2 speaks it (local/voice_server.py)
        assert re.fullmatch(r"[a-z]{3}_[A-Z][a-z]{3}", lang.asr), code  # Omnilingual ASR's code
        assert all(PHRASES[code][line] for line in LINES) and PHRASES[code][f"Okay, I'll speak {lang.name} now."]
        assert THINGS[code]["keys"] and THINGS[code]["glasses"]
    assert set(CRISIS) == set(MORE)


@pytest.mark.parametrize("code", sorted(MORE))
def test_the_crisis_words_are_caught_in_each_language_and_everyday_words_arent(code):
    die, live, everyday = CRISIS[code]
    assert crisis(die) and crisis(live) and not crisis(everyday)


@pytest.mark.parametrize("text,to", [("Andy, speak Russian", "ru"), ("talk to me in Mandarin", "zh"), ("speak Chinese", "zh"),
                                     ("in Tagalog, please", "tl"), ("reply in Vietnamese", "vi"), ("speak Filipino", "tl"),
                                     ("Say English", "en"), ("Andy, say Korean", "ko"), ("I'd say French is lovely", None),
                                     ("I can't speak German", None)])
def test_asking_for_any_language(text, to):
    assert asked_for(text) == to


class Glimmer(Translator):
    """Glimmer's answers from a table; the first answer to a sentence can be set to come back unchanged."""

    def __init__(self, table, copies=()):
        super().__init__()
        self.table, self.copies, self.asked = table, set(copies), []

    def _translate(self, system, text, examples=()):
        self.asked.append((text, bool(examples)))
        if text in self.copies and not examples:
            return text  # copied back, as Glimmer did with "Okay." in Vietnamese and one request in four
        return self.table.get(text, text)


def test_a_translation_that_comes_back_unchanged_is_tried_again_with_an_example():
    g = Glimmer({"kính của tôi đâu rồi": "where are my glasses"}, copies=["kính của tôi đâu rồi"])
    assert g.to_english("kính của tôi đâu rồi", "vi") == "where are my glasses"
    assert g.asked == [("kính của tôi đâu rồi", False), ("kính của tôi đâu rồi", True)]
    assert unchanged("Okay.", "okay") and not unchanged("Okay.", "Vâng.")


def test_andy_hears_and_speaks_russian_and_the_tv_follows(tmp_path):
    table = {"где мои очки": "where are my glasses", "I see your glasses, to my right.": "Вижу ваши очки, справа от меня."}
    a, body, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(table), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    assert a.hear("Andy, speak Russian").endswith("Okay, I'll speak Russian now.")
    assert a.language == "ru" and a.voice.voice == "rus" and a.asr_language == "rus_Cyrl"
    said = [e[1] for e in body.log if e[0] == "say"]
    assert "Хорошо, теперь я буду говорить по-русски." in said  # by hand, never translated
    snap = a.screen.snapshot()
    assert snap["language"] == "Русский · на этом компьютере" and snap["lang"] == "ru"
    assert set(snap.get("chrome", {})) <= set(chrome_words())  # the TV's labels, as translated so far
    body.log.clear()
    a.hear("где мои очки")
    said = [e[1] for e in body.log if e[0] == "say"]
    assert said[0] == "Сейчас поищу." and said[-1].startswith("Вон они!")  # the short lines by hand
    a.hear("speak English")
    assert a.language == "en" and a.voice.voice == "eng"


def test_the_crisis_reply_in_each_language_is_by_hand():
    g = Glimmer({})
    for code in MORE:
        assert g.spoken(CRISIS_REPLY, code, DISCLOSURE, CRISIS_REPLY) == LANGUAGES[code].crisis
        assert g.spoken(DISCLOSURE + " Okay.", code, DISCLOSURE, CRISIS_REPLY) == f"{LANGUAGES[code].disclosure} {PHRASES[code]['Okay.']}"
    assert g.asked == []  # no model was asked for either


@pytest.mark.parametrize("text,kind", [("did I forget my keys?", "going_out"), ("did I forget anything?", "going_out"),
                                       ("don't forget my umbrella", "chat"), ("forget my keys", "forget"),
                                       ("Did you see my keys?", "find"), ("Watch my wallet", "watch"),
                                       ("Look after my wallet", "watch"), ("watch the news", "world"), ("mind the gap", "chat"),
                                       # how Glimmer put Vietnamese (Nov 1), and what mustn't be taken for a search
                                       ("Do you see my keys?", "find"), ("did I bring everything when I came out here?",
                                                                         "going_out"),
                                       ("do you see what I mean?", "chat"), ("can you see what I mean?", "chat"),
                                       # Glimmer's curly apostrophes, and how it put Russian
                                       ("Where’s my phone?", "find"), ("I’m leaving, I’ve got everything?", "going_out"),
                                       ("Didn’t you see my keys?", "find"), ("Which time is it?", "time")])
def test_what_translations_say_reaches_the_right_ability_and_never_deletes_by_mistake(text, kind):
    assert parse(text).kind == kind


def test_the_tvs_labels_keep_the_things_hand_written_name_and_are_tried_again_when_copied_back():
    from heyandy_meta.companion.language import TVWords

    class Labels(Translator):
        def __init__(self):
            super().__init__()
            self.systems = []

        def _translate(self, system, text, examples=()):
            self.systems.append(system)
            if text == "Next" and not examples:
                return "Next"  # copied back, as Glimmer did with six of the TV's labels in Mandarin (Nov 1)
            return {"Next": "下一条提醒", "seen 25 minutes ago": "25分钟前见过", "away": "距离"}.get(text, text)

    g = Labels()
    tv = TVWords(g, "zh")
    assert tv.label("remote: seen 25 minutes ago") == "遥控器：25分钟前见过"  # Glimmer alone said 远程 ("remote access")
    assert tv.label("Next") == "下一条提醒"
    assert tv.label("away") == "距离" and "how far a thing is" in g.systems[-1]  # told what the one word means


@pytest.mark.parametrize("heard,code", [  # what Omnilingual ASR wrote, told no language (Andy's own voice, Nov 1)
    ("andy where are my glasses", "en"), ("andi dondestan mis gafas", "es"), ("安迪我的眼睛在哪里", "zh"),
    ("andi na saan ang salamin ko", "tl"), ("anh đi kim của tôi đau rồi", "vi"), ("энди где май очки", "ru"),
    ("andy onde estão meus óculos", "pt"), ("andy où sont mes lunettes", "fr"), ("handy wo ist meine brille", "de"),
    ("Енді, де мої окуляри", "uk"), ("andy dove sono i miei occhiali", "it"), ("andy gdzie są moje okulary", "pl"),
    # too little to go on: no guess (a Latin-letter guess at Korean; Italian garbled into Portuguese letters)
    ("andy dean jong otiso", None), ("ãndi duvi sõni mi o kiani", None), ("andy donderstand miss governs", None)])
def test_which_language_some_words_are_in(heard, code):
    from heyandy_meta.companion.language import heard_in

    assert heard_in(heard) == code


class Listening:
    """Andy, as the voice loop sees it: a language, and a switch."""

    def __init__(self, language="en"):
        self.language, self.heard, self.switched, self.said = language, [], [], []
        self.body = SimpleNamespace(look=lambda *a, **k: None)

    @property
    def asr_language(self):
        return LANGUAGES[self.language].asr

    def notice_language(self, to):
        self.switched.append(to)
        self.language = to

    def hear(self, text):
        self.heard.append(text)
        return "ok"

    def say(self, text):
        self.said.append(text)

    def turn_to_person(self, *a):
        pass


class Ears:
    """Omnilingual ASR on one utterance: what it writes told English, told nothing, and told Mandarin."""

    def __init__(self, told_english, untold, told_mandarin=""):
        self.language, self.asked = "eng_Latn", []
        self.out = {"eng_Latn": told_english, "auto": untold, "cmn_Hans": told_mandarin}

    def transcribe(self, samples, rate=16000, language=None):
        self.asked.append(language or self.language)
        return self.out[language or self.language]


def test_called_in_mandarin_andy_switches_says_so_and_answers_in_it():
    from heyandy_meta.voice.loop import VoiceLoop

    andy, ears = Listening(), Ears("and he the angel of this so", "安迪我的眼睛在哪里", "安迪，我的眼镜在哪里")
    loop = VoiceLoop(andy)
    text = loop._which_language("and he the angel of this so", None, ears)
    assert andy.switched == ["zh"] and ears.asked == ["auto", "cmn_Hans"] and ears.language == "cmn_Hans"
    assert loop.heard(text) == "ok" and andy.heard == ["我的眼镜在哪里"]  # the native name is Andy's name too


def test_a_request_understood_in_english_is_never_asked_again_and_background_talk_stays_dropped():
    from heyandy_meta.voice.loop import VoiceLoop

    andy, ears = Listening(), Ears("andy where are my keys", "should not be asked")
    assert VoiceLoop(andy)._which_language("andy where are my keys", None, ears) == "andy where are my keys"
    assert VoiceLoop(andy)._which_language("我们明天去公园吧", None, ears) == "我们明天去公园吧"  # not for Andy
    assert ears.asked == [] and andy.switched == []


def test_from_spanish_only_to_english_or_a_language_with_its_own_script():
    from heyandy_meta.voice.loop import VoiceLoop

    andy = Listening("es")
    ears = Ears("andi dove sono", "andy dove sono i miei occhiali")  # Italian? or Spanish misheard: not worth the risk
    ears.out["spa_Latn"] = ears.out.pop("eng_Latn"); ears.language = "spa_Latn"
    VoiceLoop(andy)._which_language("andi dove sono", None, ears)
    assert andy.switched == []
    ears.out["auto"] = "andy where are my glasses"
    ears.out["eng_Latn"] = "andy where are my glasses"
    VoiceLoop(andy)._which_language("andi wer ar mai glasses", None, ears)
    assert andy.switched == ["en"]


def test_noticing_a_language_says_so_by_hand_in_it(tmp_path):
    a, body, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer({}), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.notice_language("zh")
    said = [e[1] for e in body.log if e[0] == "say"]
    assert a.language == "zh" and said == [PHRASES["zh"]["Okay, I'll speak Chinese now."]] and a.translator.asked == []
