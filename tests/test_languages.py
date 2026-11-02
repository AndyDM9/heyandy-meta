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


def test_from_another_language_only_back_to_english():
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


def test_a_forget_heard_in_another_language_asks_first_and_a_mistranslation_deletes_nothing(tmp_path):
    """Glimmer put Korean "I've given away my things because I won't need them" as "forget my things" (Nov 1): in
    another language, forgetting asks first, and only what Andy remembers can be forgotten at all."""
    table = {"열쇠는 잊어버려": "forget my keys", "네": "Yes.", "물건들을 다 나눠 줬어요": "forget my things"}
    a, body, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer(table), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.places.watch("keys")
    a.language = "ko"
    a.hear("물건들을 다 나눠 줬어요")
    said = [e[1] for e in body.log if e[0] == "say"]
    assert "nothing to forget" in said[-1] and a.places.watching() == ["keys"]  # nothing called "things": nothing deleted
    a.hear("열쇠는 잊어버려")
    assert a.places.watching() == ["keys"]  # asked, not done
    a.hear("네")
    assert a.places.watching() == []  # the yes forgets
    a.language = "en"
    a.places.watch("wallet")
    a.hear("forget my wallet")
    assert a.places.watching() == []  # in English, said directly, at once as before


def test_in_mandarin_andy_speak_english_said_in_english_brings_english_back():
    from heyandy_meta.voice.loop import VoiceLoop

    andy = Listening("zh")
    ears = Ears("", "andy speak english")
    ears.out["cmn_Hans"] = "安迪 斯皮克 英格利"  # told Mandarin, English speech comes out as Mandarin sounds
    ears.language = "cmn_Hans"
    ears.out["eng_Latn"] = "andy speak english"
    text = VoiceLoop(andy)._which_language("安迪 斯皮克 英格利", None, ears)
    assert text == "andy speak english" and ears.asked[-1] == "eng_Latn"  # heard again in English, for the turn
    assert andy.switched == []  # the turn's own "speak English" switches, and says so once (on the robot: said twice)


def test_after_a_find_an_english_no_no_never_switches_language():
    """Found by review (Nov 1): "no, no, not that one" in the follow-up after a find was heard as Spanish (two "no"s),
    and "as far as I know, yes" as French. Each word counts once now, and English is left only when Andy was called."""
    from heyandy_meta.companion.language import heard_in
    from heyandy_meta.voice.loop import VoiceLoop

    assert heard_in("No, no, not that one.") is None and heard_in("As far as I know, yes.") is None
    andy, ears = Listening(), Ears("no no not that one", "no, no, not that one")
    loop = VoiceLoop(andy)
    loop.awake_until, loop.follow_ups_left = float("inf"), loop.follow_ups  # just answered: what follows counts without the name
    assert loop._which_language("no no not that one", None, ears) == "no no not that one" and andy.switched == []
    ears.out["auto"] = "dónde están mis gafas"  # real Spanish, but not called: English stays
    assert loop._which_language("donde estan mis gafas", None, ears) == "donde estan mis gafas" and andy.switched == []


def test_crisis_words_heard_only_when_listened_to_again_come_first_and_nothing_before_them():
    from heyandy_meta.companion.safety import crisis
    from heyandy_meta.voice.loop import VoiceLoop

    andy, ears = Listening(), Ears("and he juke ship of", "앤디, 죽고 싶어요")  # Korean: "Andy, I want to die"
    andy.set_language = lambda to: setattr(andy, "language", to) or ""
    text = VoiceLoop(andy)._which_language("and he juke ship of", None, ears)
    assert crisis(text) and andy.switched == [] and andy.language == "ko"  # no "Okay, I'll speak Korean now" first
    andy, ears = Listening(), Ears("andy kiero morir", "Andy, quiero morir")  # too short to name a language
    assert VoiceLoop(andy)._which_language("andy kiero morir", None, ears) == "Andy, quiero morir"


def test_in_ukrainian_a_second_listening_written_as_russian_never_switches_to_russian():
    from heyandy_meta.voice.loop import VoiceLoop

    andy = Listening("uk")
    ears = Ears("", "энди где мои очки")  # told nothing, Omnilingual ASR wrote Ukrainian speech as Russian
    ears.out[LANGUAGES["uk"].asr] = "енді де мої окуляри"
    ears.language = LANGUAGES["uk"].asr
    VoiceLoop(andy)._which_language("енді де мої окуляри", None, ears)
    assert andy.switched == [] and andy.language == "uk"


def test_answer_only_to_hey_andy_holds_for_other_languages_too():
    from heyandy_meta.voice.loop import VoiceLoop

    andy, ears = Listening(), Ears("andy wo de yan jing zai na li", "安迪我的眼镜在哪里")
    andy.hey_only = True  # a plain "Andy" may be a person in the house
    assert VoiceLoop(andy)._which_language("andy wo de yan jing zai na li", None, ears) == "andy wo de yan jing zai na li"
    assert ears.asked == [] and andy.switched == []


def test_speak_chinese_said_in_chinese_is_answered_once(tmp_path):
    a, body, _ = andy(Thing("glasses", -48.0, 22.0), tmp_path=tmp_path)
    a.translator, a.voice = Glimmer({"安迪，说中文": "Speak Chinese."}), SimpleNamespace(voice="eng", speed=1.0, loudness=-21.0)
    a.notice_language("zh")  # the voice loop noticed it, and said so
    a.hear("安迪，说中文")  # then the words themselves ask for it
    said = [e[1] for e in body.log if e[0] == "say"]
    # the switch, then only the AI disclosure that starts a conversation: not "I'm already speaking Chinese" after it
    assert said == [PHRASES["zh"]["Okay, I'll speak Chinese now."], LANGUAGES["zh"].disclosure]
