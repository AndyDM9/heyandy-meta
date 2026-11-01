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
# Warning signs said another way, in English: on the person's words, and on every translation into English, which is
# how most of Andy's languages reach this check. Measured (evals/crisis_languages.py, November 1): a translation of
# "I've been saving my pills for when I'm ready" came back in a dozen wordings ("putting the pills aside until I am
# ready", "collecting my medicines for the day I'm ready") and "everyone would be better off without me" as "would live
# better without me", "better for everyone if I'm gone". Never "take my pills", never "ready for bed".
PILLS = r"(?:pills?|tablets?|medicines?|medications?|meds)"
READY = r"(?:I'?m|I am|I'?ll be|I will be|I'?d be) ready\b(?!\s+(?:to|for)\b)"
CRISIS_SIGNS = re.compile(
    r"\b(?:sav|collect|gather|hoard|stockpil|stash|accumulat)\w*\b[^.?!]{0,30}\b" + PILLS + r"\b[^.?!]{0,45}\b" + READY +
    r"|\b" + READY + r"[^.?!]{0,30}\b(?:sav|collect|gather|hoard|stockpil|stash|accumulat)\w*\b[^.?!]{0,30}\b" + PILLS + r"\b"
    r"|\b(?:put|putting|set|setting)\b[^.?!]{0,25}\b" + PILLS + r"\b[^.?!]{0,15}\b(?:aside|away|off)\b[^.?!]{0,40}\b" + READY +
    r"|\b(?:everyone|everybody|they|my family|all of you|people)\b[^.?!]{0,40}\b(?:better|happier)\b[^.?!]{0,25}\bwithout me\b"
    r"|\bbetter\b[^.?!]{0,30}\bif I(?:'m| am| was| were)? (?:gone|dead|not here|not around)\b"
    r"|\bif I (?:weren'?t|wasn'?t|were not|was not) (?:here|around|alive)\b[^.?!]{0,40}\b(?:better|happier)\b"
    # three of the warning signs the 988 Lifeline lists ("know the signs"): being a burden to others, giving away
    # possessions, wanting to sleep forever. Said as a plan, not a passing remark: "I could sleep forever" isn't one.
    r"|\b(?:won'?t|will not|not going to|no longer) be a burden\b|\bbe a burden to no ?one\b"
    r"|\b(?:(?:gave|given|giving|give) (?:away|out)|distribut\w*|handed out)\b[^.?!]{0,35}\b(?:things|stuff|belongings|"
    r"possessions|everything)\b[^.?!]{0,45}\b(?:won'?t|will not|no longer|not going to|don'?t) need\b"
    r"|\b(?:want|wish|'d like|would like|longing) to (?:sleep|fall asleep|go to sleep) (?:forever|for good|and (?:not|never) wake)",
    re.IGNORECASE)


# No health advice (the README's promise, and the organizers' condition for the entry, October 30), kept in code as the
# crisis reply is: a symptom said, or a question about a medicine, a condition, a reading or how someone feels, gets
# Andy's own words, written by hand in each of its languages, and never reaches a model, on this computer or in the
# cloud. Before this (November 1), Muse Spark, asked to "explain what a statin does", explained it. Conversation only:
# "where are my pills?" is still a search, "remind me at 8 to take my pills" a reminder. Read on the English (in another
# language, the translation of it), after the crisis checks. Measured: evals/no_advice.py.
HEALTH_REPLY = ("I'm a robot, so I can't give health advice: your doctor or pharmacist can. I can remind you to call "
                "them. If it's an emergency, please call 911.")
FEELINGS_REPLY = ("I'm sorry it's hard right now. I'm a robot, so I can't give advice about how you feel, but your "
                  "doctor can. You can call or text 988 any time, day or night.")
_BODY = r"(?:\w+\s+){0,2}"  # "my (left) knee", "my lower back"
SYMPTOM = re.compile(
    r"\b(?:my|his|her)\s+" + _BODY + r"(?:hurts?|is hurting|are hurting|aches?|is aching|are aching|is sore|are sore|"
    r"(?:is|are|has been|have been|keeps?|look|looks|feel|feels) (?:swollen|sore|bleeding|numb|itchy|hurting|aching|"
    r"blurry|puffy|inflamed|infected|swelling)|swells?|bleeds?|itch(?:es)?|cramps?|throbs?|is killing me|are killing me)\b"
    r"|\bi(?:'ve| have| had)?\s+(?:got |have |had |a |an |some )*(?:headaches?|migraines?|(?:a )?fever|a temperature|"
    r"a cough|coughing|a cold|sore throat|a rash|(?:stomach|tummy|tooth|back|ear)\s?aches?|chest pains?|pains?|cramps?|"
    r"heartburn|indigestion|diarrh\w*|nausea|the flu|covid|an infection|a lump|a bruise|a blister|swelling)\b"
    r"|\bi(?:'m| am| was)?\s*(?:feel|felt|feeling|keep feeling|getting|am getting)\s+(?:so |really |very |a bit |a little |"
    r"kind of |quite )*(?:dizzy|light-?headed|faint|sick(?! of| and tired)|nauseous|feverish|weak|short of breath|"
    r"breathless|numb|achy|shaky|unwell|ill|poorly|bloated)\b"
    r"|\bi(?:'m| am)\s+(?:so |really |very |a bit |a little )*(?:dizzy|light-?headed|nauseous|feverish|short of breath|"
    r"unwell|in (?:a lot of |so much )?pain)\b"
    r"|\b(?:can'?t|cannot|hard to|trouble|difficulty)\s+(?:breathe|breathing|swallow\w*|sleep\w*|pee\w*|feel my)\b"
    r"|\b(?:i|i've|i have|he|she)\s+(?:just\s+)?(?:fell|fallen|fainted|passed out|blacked out|threw up|"
    r"been (?:throwing up|vomiting|coughing))\b"
    r"|\b(?:heartburn|indigestion|constipat\w*|diarrh\w*|nause\w*|migraines?|vertigo|incontinen\w*|headaches?|"
    r"toothaches?|backaches?|stomach ?aches?|earaches?|fever)\b"
    # the held-out set's misses (November 1), added after it was measured: always tired, a mole, a bad knee
    r"|\b(?:always|constantly) (?:tired|exhausted)\b|\b(?:tired|exhausted) all the time\b"
    r"|\bsore (?:throat|back|knees?|neck|shoulders?|feet|legs?|arms?|hips?|joints?|muscles?|eyes?|gums?|teeth|tooth)\b"
    r"|\bchest (?:pains?|feels tight|is tight|hurts)\b|\btight chest\b|\bheart (?:is )?(?:racing|pounding)\b|"
    r"\bpalpitations\b|\bblurr(?:y|ed) vision\b|\bslurr(?:ed|ing)\b", re.I)
MEDICAL = re.compile(
    r"\b(?:pills?|tablets?|capsules?|medicines?|medications?|meds|drugs?(?! ?stores?)|doses?|dosage|prescriptions?|"
    r"tylenol|acetaminophen|paracetamol|ibuprofen|advil|motrin|aleve|naproxen|aspirin|statins?|lipitor|atorvastatin|"
    r"metformin|insulin|warfarin|eliquis|blood thinners?|antibiotics?|antidepressants?|melatonin|sleeping pills?|"
    r"painkillers?|pain relievers?|opioids?|vitamins?|supplements?|inhalers?|antacids?|laxatives?|benadryl|"
    r"antihistamines?|side effects?|blood pressure|blood sugar|glucose|cholesterol|a1c|heart rate|pulse|diabet\w*|"
    r"heart (?:attack|disease|failure|condition|problems?)|strokes?|cancer|tumou?rs?|arthritis|dementia|alzheimer'?s?|"
    r"parkinson'?s?|asthma|copd|kidneys?|liver|thyroid|infections?|flu|covid|pneumonia|allerg(?:y|ies|ic)|"
    r"osteoporosis|symptoms?|diagnos\w*|treatments?|surgery|(?:test|lab|blood) results|x-?rays?|mri|blood tests?|"
    r"calories|lose weight|my weight|my diet|diet for|vaccines?|depress\w*|anxiety|insomnia|health|healthy|my heart|"
    r"the er|emergency room|urgent care|put me on|prescribed|urine|pee|stool|bowels?|phlegm|mucus|blood in|"
    r"(?:a|my) cold(?!\s+(?:day|night|morning|evening|drink|beer|one|front|snap|spell|wind|room|shower|glass|water))|"
    r"(?:good|bad|healthy|unhealthy) for me|moles?|lumps?|bad (?:knee|back|hip|leg|shoulder|heart)|"
    r"(?:hours of|enough|how much) sleep|memory (?:loss|problems?)|forgetting (?:words|names)|"
    r"see (?:a doctor|someone|a specialist)|"
    r"\w{2,}(?:pril|olol|sartan|prazole|mycin|cillin|azepam|oxetine|dipine|formin|vastatin))\b", re.I)
ASKING = re.compile(
    r"\?\s*$|^\W*(?:(?:hey|hi|ok|okay)\W+)?(?:andy\W+)?(?:how|what|what's|whats|why|which|when|should|shall|can|could|"
    r"is|are|do|does|will|would|may|might|am)\b|\b(?:should i|can i|could i|do i need|is it (?:ok|okay|safe|bad|good|"
    r"normal|dangerous|serious|alright|all right)|is that (?:ok|okay|safe|bad|good|normal|dangerous|serious|high|low|too)|"
    r"how (?:much|many|often|long)|what (?:should|can|do) i|tell me about|explain|compare|what (?:is|are|does|do)|"
    r"what's|whats|worried|concerned|scared|afraid|good for|bad for|safe to|ok(?:ay)? to|help (?:with|for)|"
    r"anything for|something for|recommend|suggest|advice|advise|mean|means)\b", re.I)
FEELING = re.compile(
    r"\b(?:i(?:'m| am)|i(?:'ve| have) been|i feel|i'm feeling|i am feeling|i keep feeling|i get|feeling)\s+"
    r"(?:so |really |very |quite |a bit |a little |kind of |kinda |pretty |too |always |constantly )*"
    r"(?:down|low|depressed|anxious|panicky|hopeless|worthless|miserable)\b(?! (?:on|of|to|for|with|here|there|stairs)\b)"
    r"|\b(?:my|i have|i've got|i get|i'm having) (?:depression|anxiety|panic attacks?)\b"
    r"|\b(?:am i|do you think i'?m|i think i'?m|i might be) depressed\b"
    # the first held-out set's misses: how to stop worrying, nothing makes me happy (a sign the 988 Lifeline lists)
    r"|\b(?:stop|quit) (?:worrying|being (?:so )?(?:anxious|sad|down))\b|\bworry (?:all the time|constantly|so much)\b"
    r"|\bnothing (?:makes me happy|makes me smile|brings me joy|feels good)\b|\bdon'?t enjoy anything\b"
    r"|\b(?:can'?t stop|keep) crying\b|\bcry all the time\b"
    r"|\bhelp me (?:relax|calm down|feel better|stop worrying|cope)\b|\b(?:so|really|very|too) stressed\b"
    # sad, unhappy or lonely for a while (in other languages "feeling down" came back from translation as "sad"):
    # not "I'm sad my team lost"
    r"|\b(?:sad|unhappy|lonely)\b[^.?!]{0,25}\b(?:lately|these (?:past )?(?:few )?days|these days|for (?:days|weeks|months)|"
    r"all the time|every day|most days|since)\b|\b(?:lately|these days|for weeks|most days|every day)\b[^.?!]{0,25}"
    r"\b(?:sad|unhappy|lonely)\b", re.I)
# Muse Glimmer, translating, declined a health question ("मेरी पीठ में दर्द है, मुझे क्या लेना चाहिए?" came back as "I
# can't provide medical advice."): its refusal says what the question was
REFUSED_HEALTH = re.compile(r"^\W*(?:I'?m sorry\W+(?:but\s+)?)?I (?:can'?t|cannot|won'?t|am unable to|'m unable to) "
                            r"(?:provide|give|offer|help with) (?:any |you )?(?:medical|health|medication|dosage)", re.I)
# not a question about health, though it names a medicine: did I take them (Andy can't know; the model says so), where
NOT_HEALTH = re.compile(r"\bdid i (?:take|have|forget|miss)\b|\b(?:on|in|under|behind|next to|by) the (?:table|counter|"
                        r"shelf|desk|drawer|kitchen|bathroom|bedroom|cabinet|cupboard|sofa|couch|floor|bed|nightstand)\b",
                        re.I)


def health(text: str) -> str | None:
    """"Can I take ibuprofen with my blood pressure pills?" and "my knee is swollen" -> HEALTH_REPLY; "I've been
    feeling down" -> FEELINGS_REPLY; "I took my pills", "tell me a joke" -> None (conversation, as before)."""
    t = (text or "").replace("\u2019", "'")
    if REFUSED_HEALTH.search(t):
        return HEALTH_REPLY
    if FEELING.search(t):
        return FEELINGS_REPLY
    if SYMPTOM.search(t):  # "I fell in the bathroom" is one wherever it was
        return HEALTH_REPLY
    if MEDICAL.search(t) and ASKING.search(t) and not NOT_HEALTH.search(t):
        return HEALTH_REPLY
    return None


def crisis(text: str) -> bool:
    t = unicodedata.normalize("NFC", text or "")  # one way to write "ế", whichever the keyboard or hearing used
    t = t.replace("\u2019", "'").replace("\u2018", "'")  # speech-to-text and keyboards write ’ too
    return bool(CRISIS.search(t) or CRISIS_ANY.search(t) or CRISIS_SIGNS.search(t))


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
