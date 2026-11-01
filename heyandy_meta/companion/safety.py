"""Saying it's an AI, and the crisis protocol. Both run in code, before and outside any model.

US companion-chatbot laws (California SB 243, in effect 2026-01-01; New York, in effect 2025-11-05) ask a companion
to say it's an AI at the start and at least every three hours, and to refer anyone who talks about harming
themselves to crisis services. Andy does exactly that, and nothing more: it never counsels. The protocol is
published in docs/crisis-protocol.md.
"""
import re
import time
import unicodedata

DISCLOSURE = "I'm Andy, an AI robot."
EVERY_S = 3 * 3600
NEW_CONVERSATION_AFTER_S = 30 * 60

CRISIS_REPLY = ("I'm a robot, so I can't help with this the way a person can. You can call or text 988, the Suicide "
                "and Crisis Lifeline, any time, day or night. If you're in danger right now, please call 911.")
CRISIS = re.compile(
    r"\b(kill(ing)? myself|end(ing)? (it all|my (own )?life)|tak(e|ing) my (own )?life|suicid\w*|hurt(ing)? myself"
    r"|harm(ing)? myself|self[- ]harm|(hang|shoot|drown|cut)(ing)? myself|overdos(e|ing) on purpose"
    r"|(don'?t|do not|no longer) want to (live|be alive|be here|wake up)|(want|going) to die|wanna die|better off dead"
    r"|wish (i was|i were|i'?d) (dead|never born)|life (isn'?t|is not|'s not|ain'?t) worth (it|living)|no reason to (live|go on)"
    r"|can'?t go on (anymore|any more|living)|end(ing)? it (all )?(tonight|today|now)|better off without me"
    r"|(sleep|go to sleep) and (never|not) wake up|never wake up again|disappear (forever|for good)"
    # Spanish (Andy can speak it): checked on the person's own words, before any translation
    r"|suicid[ao]r(me|se)?|matarme|quitarme la vida|lastimarme|hacerme da[nñ]o"
    r"|me (quiero|voy a|pienso|deseo) (matar|suicidar|morir|quitar la vida|hacer da[nñ]o|lastimar)"
    r"|(acabar|terminar) con (todo|mi vida)|no quiero (vivir|seguir viviendo|estar aqu[ií]|seguir aqu[ií])"
    r"|quiero morir(me)?|quisiera morir(me)?|ganas de morir(me)?|(estar[ií]a|quisiera estar|mejor) muert[oa]"
    r"|quisiera estar muert[oa]|ser[ií]a mejor estar muert[oa]|no vale la pena vivir|no tengo raz[oó]n para vivir"
    r"|(estar[ií]an|vivir[ií]an) mejor sin m[ií]|desaparecer para siempre|no (volver a )?despertar(me)?)\b",
    re.IGNORECASE)


# The other languages Andy speaks (companion/languages.py), by hand, checked on the person's own words before any
# model reads them (the translator too). Matched anywhere in the words, not as whole words: Chinese has no spaces,
# Korean and Arabic join small words on, and Russian, Ukrainian and Polish change their endings. Only phrases that
# mean harming oneself; a figure of speech ("I could die of boredom") may get the crisis reply, which is the safe way
# to be wrong. A native speaker should read each list (docs/research.md, 54).
CRISIS_MORE = {
    "zh": "自杀|自殺|轻生|輕生|寻死|尋死|想死|不想活|活不下去|结束生命|結束生命|结束自己的生命|了结自己|了結自己|伤害自己|傷害自己",
    "tl": "magpakamatay|nagpapakamatay|papatayin ko ang sarili|patayin ang sarili ko|gusto ko nang mamatay|"
          "gusto kong mamatay|ayoko nang mabuhay|ayaw ko nang mabuhay|saktan ang sarili ko|wakasan ang buhay ko",
    "vi": "tự tử|tự sát|muốn chết|không muốn sống|kết liễu đời|tự làm hại bản thân|tự hại mình",
    "ko": "자살|죽고 싶|죽고싶|살고 싶지 않|살기 싫|목숨을 끊|삶을 끝내|자해",
    "ru": "самоубий|суицид|покончить с собой|покончу с собой|убить себя|убью себя|хочу умереть|не хочу жить|"
          "жить не хочу|не хочу больше жить|свести сч[её]ты с жизнью|причинить себе вред|лучше бы я умер",
    "ar": "انتحار|أنتحر|انتحر|أقتل نفسي|اقتل نفسي|أريد أن أموت|اريد ان اموت|أريد الموت|اريد الموت|لا أريد أن أعيش|"
          "لا اريد ان اعيش|أنهي حياتي|انهي حياتي|أؤذي نفسي|اؤذي نفسي",
    "hi": "आत्महत्या|ख़ुदकुशी|खुदकुशी|मरना चाहता|मरना चाहती|जीना नहीं चाहता|जीना नहीं चाहती|ख़ुद को मार|खुद को मार|"
          "अपनी जान ले|ख़ुद को नुक़सान|खुद को नुकसान",
    "pt": "suicid|me matar|matar-me|tirar a minha vida|tirar minha vida|tirar minha própria vida|quero morrer|"
          "não quero mais viver|não quero viver|acabar com a minha vida|acabar com minha vida|me machucar",
    "fr": "suicid|me tuer|en finir avec la vie|mettre fin à mes jours|mettre fin à ma vie|je veux mourir|"
          "envie de mourir|je ne veux plus vivre|me faire du mal",
    "it": "suicid|uccidermi|ammazzarmi|togliermi la vita|farla finita|voglio morire|non voglio più vivere|farmi del male",
    "pl": "samobój|zabić się|zabiję się|odebrać sobie życie|chcę umrzeć|nie chcę żyć|nie chcę już żyć|"
          "zrobić sobie krzywdę|skrzywdzić siebie",
    "de": "selbstmord|suizid|mich umbringen|mir das leben nehmen|will sterben|will nicht mehr leben|"
          "nicht mehr leben will|mir etwas antun|mich selbst verletzen|lebensmüde",
    "uk": "самогубств|суїцид|покінчити з собою|покінчу з собою|вбити себе|уб'ю себе|хочу померти|не хочу жити|"
          "жити не хочу|звести рахунки з життям|заподіяти собі шкоду",
}
CRISIS_ANY = re.compile("|".join(CRISIS_MORE.values()), re.IGNORECASE)


def crisis(text: str) -> bool:
    t = unicodedata.normalize("NFC", text or "")  # one way to write "ế", whichever the keyboard or hearing used
    t = t.replace("\u2019", "'").replace("\u2018", "'")  # speech-to-text and keyboards write ’ too
    return bool(CRISIS.search(t) or CRISIS_ANY.search(t))


class Disclosure:
    """Says "I'm Andy, an AI robot." at the start of a conversation and again every three hours."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self.last_said = self.last_turn = float("-inf")

    def prefix(self) -> str:
        now = self._clock()
        due = now - self.last_turn > NEW_CONVERSATION_AFTER_S or now - self.last_said >= EVERY_S
        self.last_turn = now
        if due:
            self.last_said = now
            return DISCLOSURE + " "
        return ""


def respond(text: str, answer, disclosure: Disclosure, opening=None, flagged: bool = False) -> str:
    """The one entry point for a spoken turn: the crisis reply bypasses the model; otherwise the model answers.
    opening, if given, is handed the AI disclosure before the answer is made, so it can be said at once. flagged: the
    second check (Llama Guard on this computer, safety_model.py) heard it where the word list didn't."""
    if flagged or crisis(text):
        disclosure.last_said = disclosure.last_turn = disclosure._clock()
        return CRISIS_REPLY
    prefix = disclosure.prefix()
    if prefix and opening:
        opening(prefix)
    return prefix + answer(text)
