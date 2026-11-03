import pytest

from heyandy_meta.voice.spoken import number, phrases, words


def test_numbers_in_words_in_english_and_spanish():
    assert number(5) == "five" and number(42) == "forty-two" and number(115) == "one hundred fifteen"
    assert number(2026) == "two thousand twenty-six"
    assert number(21, "es") == "veintiuno" and number(45, "es") == "cuarenta y cinco"
    assert number(100, "es") == "cien" and number(1500, "es") == "mil quinientos"


def test_times_units_and_abbreviations_are_said_as_people_say_them():
    assert words("Remind me at 3:15 pm") == "Remind me at three fifteen P M"
    assert words("It's 3:05, about 5 feet away") == "It's three oh five, about five feet away"
    assert words("72°F and 20% rain") == "seventy-two degrees and twenty percent rain"
    assert words("I'm Andy, an AI robot. OK?") == "I'm Andy, an A I robot. okay?"
    assert words("1.5 m away") == "one point five m away"
    assert words("a las 3:15", "es") == "a las tres y quince"
    assert words("a unos 1,5 metros", "es") == "a unos uno coma cinco metros"
    assert words("1,500 people") == "one thousand five hundred people"


def test_phrases_carry_the_pauses_the_punctuation_made():
    out = phrases("Oh, there they are! Your glasses are on the armchair, just to my left. Want me to keep an eye?")
    assert [p for p, _ in out] == ["Oh", "there they are", "Your glasses are on the armchair", "just to my left",
                                   "Want me to keep an eye"]
    assert [pause for _, pause in out] == [0.15, 0.32, 0.15, 0.32, 0.0]
    assert phrases("...!") == []


@pytest.mark.parametrize("lang, text, said", [
    ("en", "If you need help, please call 911 right away.", "If you need help, please call nine one one right away."),
    ("en", "You can call or text 988, the Suicide and Crisis Lifeline.", "You can call or text nine eight eight, the Suicide and Crisis Lifeline."),
    ("es", "Si necesita ayuda, llame al 911 ahora mismo.", "Si necesita ayuda, llame al nueve uno uno ahora mismo."),
    ("es", "Llame o envíe un mensaje al 988.", "Llame o envíe un mensaje al nueve ocho ocho."),
])
def test_the_numbers_andy_gives_to_call_are_said_digit_by_digit(lang, text, said):
    """November 3: Andy's voice said "please call nine hundred eleven" and "novecientos once"; emergency and crisis
    numbers are said as they're dialled."""
    assert words(text, lang) == said


def test_other_numbers_with_those_digits_are_still_numbers():
    assert words("about 9.11 metres", "en") == "about nine point one one metres"
    assert words("9110 steps", "en") == "nine thousand one hundred ten steps"

