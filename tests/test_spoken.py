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


def test_phrases_carry_the_pauses_the_punctuation_made():
    out = phrases("Oh, there they are! Your glasses are on the armchair, just to my left. Want me to keep an eye?")
    assert [p for p, _ in out] == ["Oh", "there they are", "Your glasses are on the armchair", "just to my left",
                                   "Want me to keep an eye"]
    assert [pause for _, pause in out] == [0.15, 0.32, 0.15, 0.32, 0.0]
    assert phrases("...!") == []
