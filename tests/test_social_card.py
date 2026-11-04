"""The card a shared link shows (scripts/social_card.py) and the tags that point to it (build_static_space.py)."""
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_static_space  # noqa: E402
import claims  # noqa: E402
import social_card  # noqa: E402


def test_the_card_is_the_size_x_and_github_ask_for():
    img = Image.open(social_card.OUT)
    assert img.size == (1280, 640) and social_card.OUT.stat().st_size < 1_000_000  # 2:1; GitHub's limit is 1 MB


def test_the_card_says_what_the_scorecards_say_today():
    """Made from the files; a new run that changes a figure means making it again: uv run python scripts/social_card.py"""
    assert social_card.said() == [list(f) for f in social_card.figures()]


def test_its_figures_come_from_their_sources():
    pointed, languages, models = social_card.figures()
    assert claims.unattended_since_fix() == f"{pointed[0]} unattended searches"
    assert languages[0] == "15"
    names = social_card.models()
    assert models[0] == str(len(names)) == "11" and "SAM 3.1" in names and "Muse Spark 1.3" in names


def test_a_shared_link_to_each_page_shows_the_card():
    page = "<html><head><title>Andy</title></head><body></body></html>"
    for name in build_static_space.SHARED:
        out = build_static_space.shared(page, name)
        tags = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', out))
        assert tags["og:image"] == "https://heyandy-ai-andy.static.hf.space/card.png"
        assert tags["twitter:card"] == "summary_large_image" and tags["og:image:width"] == "1280"
        assert tags["og:title"] and tags["description"] and tags["og:url"].startswith("https://")
        assert out.count("og:image\"") == 1 and out.index("</title>") < out.index("og:image")


def test_the_spaces_own_card_is_its_thumbnail():
    readme = (ROOT / "space" / "README.md").read_text().split("---")[1]
    assert "thumbnail: https://huggingface.co/spaces/heyandy-ai/andy/resolve/main/card.png" in readme


def test_the_front_door_shows_the_cards_figures_and_the_language_scorecards_own_words():
    """page.html's welcome: its numbers are the card's (made from the scorecards, checked by scripts/claims.py), and
    "where are my glasses?" in each other language is the one evals/languages.py asks: no words written for the page."""
    import build_static_space
    from evals.languages import REQUESTS

    figures, asks = build_static_space.front_door()
    assert figures == [list(f) for f in social_card.figures()]
    assert asks == [[code, asked[0]] for code, asked in REQUESTS.items()] and len(asks) == 13


def test_andys_voice_on_the_front_door_says_its_own_hand_written_words_in_each_language():
    """scripts/front_door_voice.py: Andy introducing itself in its fifteen languages, its own voice (SeamlessM4T v2),
    the words its hand-written ones (companion/language.py, DISCLOSURE): each clip's words and hash kept, and each
    heard back by Omnilingual ASR close to its words; the Space's build ships every one."""
    import hashlib
    import json

    import front_door_voice

    screen = ROOT / "heyandy_meta" / "screen" / "voice"
    clips = json.loads((screen / "voice.json").read_text())["clips"]
    lines = front_door_voice.lines()
    assert set(clips) == set(lines) and len(clips) == 15
    for code, c in clips.items():
        assert c["text"] == lines[code][0] and c["voice"] == lines[code][1]  # what the page shows is what it says
        assert hashlib.sha256((screen / f"{code}.mp3").read_bytes()).hexdigest() == c["sha256"]
        assert c["heard back"] >= 0.6 and 1.0 <= c["seconds"] <= 6.0
    assert build_static_space.voices() == {code: {"text": c["text"], "file": c["file"]} for code, c in clips.items()}


def test_the_story_told_in_andys_voice_says_no_more_than_its_chapters():
    """scripts/front_door_voice.py STORY: each chapter told in the first person, a clip per chapter with its words, its
    hash and how it was heard back; every chapter of the page's story has one, and the build ships them."""
    import hashlib
    import json
    import re

    import front_door_voice

    screen = ROOT / "heyandy_meta" / "screen"
    told = json.loads((screen / "voice" / "story.json").read_text())["chapters"]
    page = (screen / "page.html").read_text()
    titles = re.findall(r'\["[a-z-]+", \d+, "([^"]+)", "', re.search(r"const STORY = \[(.*?)\n  \];", page, re.S).group(1))
    assert set(titles) <= set(told) and "Andy, on the table" in told  # the robot's own chapter, when built with it
    for title, c in told.items():
        assert c["text"] == front_door_voice.STORY[title]
        assert hashlib.sha256((screen / c["file"]).read_bytes()).hexdigest() == c["sha256"]
        assert c["heard back"] >= 0.9 and 3.0 <= c["seconds"] <= 8.0
        assert not re.search(r"\d", c["text"].replace("3.1", "").replace("3D", "")), title  # no figure the page doesn't show
    assert build_static_space.narration() == {t: {"text": c["text"], "file": c["file"], "seconds": c["seconds"]}
                                              for t, c in told.items()}


def test_find_modes_words_are_andys_own_by_hand_in_each_language():
    """scripts/front_door_voice.py FIND: the robot's own words at find mode's moments, by hand (companion/language.py
    PHRASES), in every language that has them all; each clip's words and hash kept, heard back by Omnilingual ASR (a
    short exclamation, under 1.7 s, can be heard far from its letters, "È lì!" as "elie": kept, and said in research.md)."""
    import hashlib
    import json

    import front_door_voice

    screen = ROOT / "heyandy_meta" / "screen"
    langs = json.loads((screen / "voice" / "find.json").read_text())["languages"]
    assert langs.keys() == front_door_voice.find_lines().keys() and len(langs) == 15
    for code, moments in langs.items():
        for moment, c in moments.items():
            assert c["text"] == front_door_voice.find_lines()[code][moment]
            assert hashlib.sha256((screen / c["file"]).read_bytes()).hexdigest() == c["sha256"]
            assert c["heard back"] >= 0.6 or c["seconds"] < 1.7, (code, moment)
    assert build_static_space.find_voice()["en"]["it"] == {"text": "There it is!", "file": "voice/find-en-it.mp3"}


def test_each_demo_scene_is_said_in_andys_voice_and_its_words_are_the_scenes_own():
    """scripts/front_door_voice.py scene_lines: each scene's caption (what the TV shows Andy saying), in the scene's
    language, in Andy's own voice, sentence by sentence as the robot's speaker makes it. A scene whose words change
    without its clip made again fails here."""
    import hashlib
    import json

    import front_door_voice

    screen = ROOT / "heyandy_meta" / "screen"
    said = json.loads((screen / "voice" / "scenes.json").read_text())["scenes"]
    now = front_door_voice.scene_lines()
    assert said.keys() == now.keys() and len(said) >= 30
    for name, c in said.items():
        assert (c["text"], c["lang"]) == now[name], name
        assert hashlib.sha256((screen / c["file"]).read_bytes()).hexdigest() == c["sha256"]
        assert c["heard back"] >= 0.85, name
    assert {c["lang"] for c in said.values()} >= {"en", "es", "zh", "ko", "ar", "hi", "uk"}
    assert build_static_space.scene_voice()["in-ko"]["file"] == "voice/scene-in-ko.mp3"


def test_the_story_in_andys_other_languages_is_offered_only_where_every_chapter_passes():
    """scripts/front_door_voice.py story_in: the story (STORY) in Andy's other languages, each chapter translated by
    Muse Glimmer, said by SeamlessM4T v2 in the language's voice and heard back by Omnilingual ASR; its translation back
    into English kept beside it. A language is offered only when every chapter passes the machine's checks, and the
    build ships those alone; none is said to be checked by a native speaker until one has."""
    import hashlib
    import json

    import front_door_voice

    screen = ROOT / "heyandy_meta" / "screen"
    made = json.loads((screen / "voice" / "story-in.json").read_text())
    langs = made["languages"]
    from heyandy_meta.companion.language import LANGUAGES

    assert set(langs) == set(LANGUAGES) - {"en"} and made["checked by a native speaker"] == []
    offered = {code for code, lang in langs.items() if lang["offered"]}
    assert len(offered) >= 8
    for code, lang in langs.items():
        assert lang["chapters"].keys() == front_door_voice.STORY.keys(), code
        assert lang["names said as"] == front_door_voice.SOUNDS.get(code, {})
        for title, c in lang["chapters"].items():
            assert hashlib.sha256((screen / c["file"]).read_bytes()).hexdigest() == c["sha256"]
            assert c["said"] == front_door_voice.aloud(c["text"], lang["names said as"])  # the voice was given these words
            if lang["offered"]:
                latin = LANGUAGES[code].asr.endswith("_Latn")
                for english in {front_door_voice.STORY[title], front_door_voice.PLAINER.get(title, front_door_voice.STORY[title])}:
                    assert front_door_voice.problems(english, c["text"], latin) == [], (code, title)
                assert not c["title"] or front_door_voice.problems(title, c["title"], latin) == [], (code, title)
                assert c["heard back"] >= front_door_voice.HEARD and c["back"] and 1.0 <= c["seconds"] <= 16.0, (code, title)
        assert lang["offered"] == (lang["why not"] == []), code
    assert set(build_static_space.narration_in()) == offered
    assert build_static_space.narration_in()[sorted(offered)[0]]["Your turn"]["file"].startswith("voice/story-")


def test_a_translation_of_the_story_is_checked_by_machine_for_what_goes_wrong():
    """November 2, Glimmer's first tries: a Korean line looped into "hello" over and over, "Identical cups?" came back
    in English, Muse Glimmer was written in Arabic letters, and "You ask:" was left in English in Korean."""
    import front_door_voice as f

    cups = "Identical cups? SAM 3.1 Object Multiplex follows every one of them through the shuffle."
    assert f.problems(cups, "Identical cups? SAM 3.1 Object Multiplex sigue a cada uno.") == ["English left: identical cups"]
    assert f.problems(cups, "¿Tazas idénticas? SAM 3.1 Object Multiplex sigue a cada una al barajarlas.") == []
    assert f.problems("Muse Glimmer translates.", "ميوز غليمر يترجم.", latin=False) == ["lost Muse Glimmer"]
    assert f.problems("You ask: Hey Andy, where's my mug?", "You ask: 안녕하세요, 앤디, 제 머그컵은 어디에 있나요?", latin=False) \
        == ["English left: you ask"]
    assert "a word over and over" in f.problems("And what I never do.", "안녕하세요, " * 30, latin=False)
    assert f.problems("Five looks.", "다섯 번, 6번.", latin=False) == ["a figure the English hasn't"]
    assert f.problems("I watch your hand.", "Ich beobachte Ihre Hand.") == []  # one shared word in Latin letters may be its own
    assert f.aloud("SAM 3.1 Object Multiplex와 SAM 3.1", f.SOUNDS["ko"]) == "샘 쓰리 포인트 원 오브젝트 멀티플렉스와 샘 쓰리 포인트 원"


def test_each_space_cards_short_description_fits_hugging_faces_60_characters():
    """November 3: Andy Finder's card said 67 characters; Hugging Face takes at most 60 and refuses the upload."""
    import re

    for card in (ROOT / "space" / "README.md", ROOT / "apps" / "andy_finder" / "README.md"):
        front = card.read_text().split("---")[1]
        said = re.search(r"^short_description: (.*)$", front, re.M).group(1).strip()
        assert 0 < len(said) <= 60, (card.name, len(said), said)
