"""The TV page in a real browser: no script error, on Andy's own TV and in the public demo.

A name declared twice (2026-10-31, the public demo's ask box) stopped the whole script: the TV would have stayed blank
at the robot as well as in the demo, and no other test could see it. This one loads the page as a browser does.
Skipped where Playwright's Chromium isn't installed.
"""
import functools
import sys
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001 - no browser here: skip, as the docstring says
            pytest.skip(f"no Chromium for Playwright: {e}")
        yield b
        b.close()


def errors_on(browser, url: str, wait_ms: int = 1500, act=None) -> list[str]:
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # the page's own catch logs what stopped a render (a Chinese "：" did, Nov 1, with nothing thrown)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.goto(url)
    page.wait_for_timeout(wait_ms)
    if act:
        act(page)
    page.close()
    return errors


def test_andys_own_tv_runs_without_a_script_error(browser):
    state = ScreenState()
    state.said("There it is!", "device")
    server = serve(state, port=0)
    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/") == []
    finally:
        server.shutdown()


def test_the_public_demo_runs_and_asking_andy_plays_a_scene(browser):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    url = f"http://127.0.0.1:{server.server_address[1]}/?ask=I%27m%20ringing%20my%20phone"
    seen = {}

    def check(page):
        seen.update(page.evaluate("() => ({chosen, kicker: document.getElementById('kicker').textContent,"
                                  " routes: ['help me reach it', 'where are my keys', 'show me the room'].map(route)})"))

    try:
        assert errors_on(browser, url, 2500, check) == []
        assert seen["chosen"] == "sound" and seen["kicker"] == "Listening for your phone"
        assert seen["routes"] == ["guide", "find", "room"]
    finally:
        server.shutdown()


def test_a_health_question_typed_into_the_demo_shows_andys_own_words(browser):
    from heyandy_meta.companion.safety import HEALTH_REPLY

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import PLAYED, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in PLAYED})
    got = {}

    def typed(page_):
        got.update(page_.evaluate("() => { ask('How many Tylenol can I take?'); const h = asked; ask('I fell and I can\\'t get up');"
                                  " const e = asked; ask('Sing me a song'); return {health: h.note, other: asked.note, said: HEALTH_SAID,"
                                  " fell: e.note, fellScene: e.scene, emergency: EMERGENCY_SAID, asleep: route('I fell asleep on the sofa')}; }"))

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/", 2500, typed) == []
    finally:
        server.shutdown()
    assert got["said"] == HEALTH_REPLY and HEALTH_REPLY in got["health"] and "no model answers a health question" in got["health"]
    assert got["other"].startswith("Nothing matched that")
    from heyandy_meta.companion.safety import EMERGENCY_REPLY

    assert got["emergency"] == EMERGENCY_REPLY and got["fellScene"] == "emergency" and "from code" in got["fell"]
    assert got["asleep"] != "find"


def test_the_settings_gear_opens_its_menu_and_under_the_hood_runs(browser):
    from heyandy_meta.screen.hood import Hood

    state = ScreenState()
    state.hood = Hood()
    server = serve(state, port=0)
    seen = {}

    def gear(page):
        page.click("#gear")
        seen["menu"] = page.evaluate("() => !document.getElementById('menu').hidden")
        page.click("#m-hood")
        page.wait_for_timeout(1500)
        seen["url"], seen["title"] = page.url, page.evaluate("() => document.querySelector('h1').textContent")

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/", 1200, gear) == []
        assert seen["menu"] and seen["url"].endswith("/hood") and seen["title"] == "Under the hood"
    finally:
        server.shutdown()


def test_every_demo_scene_draws_in_full(browser):
    """Each scene of the public demo, alone: the page draws it with no error, and the found scenes show their picture
    (the Mandarin scene once stopped at the list of things, and the TV stayed half empty)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import IN_LANGUAGE, PLAYED, SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    every = PLAYED
    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in every}, listed=list(SCENES))
    shown = {}
    try:
        pictured = {"found", "mandarin", "spanish", "emergency", *IN_LANGUAGE}
        count = "() => document.querySelectorAll('#card img, #card canvas, #card svg').length"
        for name in every:
            def look(page, name=name):
                if name in pictured:  # after the Reveal: waited for, not timed (a slower machine took longer than 1.2 s)
                    try:
                        page.wait_for_function(f"({count})() > 0", timeout=8000)
                    except Exception:  # noqa: BLE001 - counted as it is below, and the assertion says which
                        pass
                shown[name] = page.evaluate(count)
            url = f"http://127.0.0.1:{server.server_address[1]}/?scene={name}"
            assert errors_on(browser, url, 1200, look) == [], name
        assert not [n for n in pictured if not shown[n]], [n for n in pictured if not shown[n]]
    finally:
        server.shutdown()


def test_asking_andy_in_any_of_its_languages_plays_that_languages_scene(browser):
    """Typed in one of Andy's fifteen languages, Ask Andy plays the find in it, as Andy notices the language it's
    called in; the page's everyday words are the same lists Andy's ears use (companion/language.py)."""
    import json
    import re

    from heyandy_meta.companion.language import EVERYDAY
    from heyandy_meta.screen.server import page

    lists = json.loads(re.search(r"const EVERYDAY = (\{.*?\});", page()).group(1))
    assert lists == EVERYDAY
    server = serve(ScreenState(), port=0)
    asked = ["我的眼镜在哪里？", "¿Dónde están mis gafas?", "Где мои очки?", "Де мої окуляри?", "내 안경 어디 있어?",
             "Où sont mes lunettes ?", "Wo ist meine Brille?", "Kính của tôi đâu rồi?", "मेरा चश्मा कहाँ है?", "أين نظارتي؟",
             "Nasaan ang salamin ko?", "Onde estão meus óculos?", "Dove sono i miei occhiali?", "Gdzie są moje okulary?",
             "Where are my keys?", "help me reach it"]
    got = {}

    def routes(page_):
        got["r"] = page_.evaluate("(qs) => qs.map(route)", asked)

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/", 1200, routes) == []
    finally:
        server.shutdown()
    assert got["r"] == ["mandarin", "spanish", "in-ru", "in-uk", "in-ko", "in-fr", "in-de", "in-vi", "in-hi", "in-ar",
                        "in-tl", "in-pt", "in-it", "in-pl", "find", "guide"]


def test_say_it_has_a_microphone_scores_phrases_by_ctc_and_snaps_near_misses(browser):
    """The demo's 🎙 (Meta's wav2vec 2.0 in the browser; evals/say_it.py measures it with the model): the phrase that
    explains the letters best wins, by the CTC forward algorithm; a word one letter off a word Andy's routes know is
    that word. No network here: the model isn't fetched, the maths is checked on made-up letter likelihoods."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    got = {}

    def check(page):
        got.update(page.evaluate("""() => {
          const V = 32, frames = (word) => [...word].flatMap((c) => {  // each letter likely for two frames, then a blank
            const row = (i) => { const r = new Float32Array(V).fill(Math.log(0.01)); r[i] = Math.log(0.69); return r; };
            return [row(LETTER[c]), row(LETTER[c]), row(0)];
          });
          const lp = frames("HI");
          return { mics: document.querySelectorAll('button.mic').length, hi: ctc(lp, letters('hi')), ho: ctc(lp, letters('ho')),
                   room: snap('show me the rom'), pass: snap('wheres my pasport'), typed: route(snap('what time is it')) };
        }"""))

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/?explore", 1500, check) == []
    finally:
        server.shutdown()
    assert got["mics"] >= 1 and got["hi"] < got["ho"]
    assert got["room"] == "show me the room" and "passport" in got["pass"]


def test_the_story_opens_on_the_robot_when_the_space_has_a_clip(browser):
    """build_static_space.py --clip: the robot itself, filmed, is the story's first chapter, over the TV, and gone after
    it; with no clip, the story is as it was."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    url = f"http://127.0.0.1:{server.server_address[1]}/?story"  # past the front door
    seen = {}
    try:
        for with_clip in (True, False):
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            if with_clip:
                page.add_init_script("window.HEYANDY_CLIP = 'robot.mp4'; window.HEYANDY_CLIP_SECONDS = 6;")
            page.goto(url)
            page.wait_for_function("document.body.classList.contains('storying')", timeout=10000)
            seen[with_clip] = page.evaluate("""() => { const first = [STORY.length, STORY[0][2], !!document.getElementById('clip')];
                                                      go(1); return [...first, !!document.getElementById('clip')]; }""")
            page.close()
    finally:
        server.shutdown()
    assert seen[True][1:] == ["Andy, on the table", True, False] and seen[True][0] == seen[False][0] + 1
    assert seen[False][2] is False and seen[False][1] == "Meet Andy"


def test_each_story_chapter_says_what_it_rests_on_and_a_phone_can_press_every_button(browser):
    """November 2: a judge's review found the story showing abilities never tried on the robot (the cup game, the hand
    guiding), and at a phone's width the story's buttons sat on top of each other. Each chapter now says, under it,
    whether it was measured on the robot or not yet; on a phone the ask box has its own row; and under a finger every
    button is at least 44 px tall (the explore bar's were 21)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    url = f"http://127.0.0.1:{server.server_address[1]}/?story"  # past the front door
    try:
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(url)
        page.wait_for_function("document.body.classList.contains('storying')", timeout=10000)
        proofs = page.evaluate("""() => STORY.map((c, i) => { go(i); const p = document.querySelector('#story .proof');
                                                             return [c[0], p ? p.className : null, p ? p.textContent : ''] })""")
        page.close()
        overlaps = {}
        for width, height in ((390, 844), (360, 740)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url)
            page.wait_for_function("document.body.classList.contains('storying')", timeout=10000)
            boxes = page.eval_on_selector_all("#story nav button", "els => els.map(e => { const r = e.getBoundingClientRect();"
                                              " return [r.left, r.top, r.right, r.bottom] })")
            overlaps[width] = [(i, j) for i, a in enumerate(boxes) for j, c in enumerate(boxes) if i < j
                               and a[0] < c[2] - 1 and c[0] < a[2] - 1 and a[1] < c[3] - 1 and c[1] < a[3] - 1]
            overlaps[f"{width} wider"] = page.evaluate("document.documentElement.scrollWidth") > width
            page.close()
        page = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)  # a finger
        page.goto(url)
        page.wait_for_function("document.body.classList.contains('storying')", timeout=10000)
        page.evaluate("exploreAll()")
        page.wait_for_timeout(300)
        smallest = page.evaluate("""() => Math.min(...[...document.querySelectorAll('#demo button, #story nav button, form.ask button')]
                                     .filter(e => e.getBoundingClientRect().height > 2).map(e => e.getBoundingClientRect().height))""")
        page.close()
    finally:
        server.shutdown()
    assert smallest >= 44  # the explore bar's scene buttons were 21 px tall on a phone
    kinds = {name: (cls or "").replace("proof ", "") for name, cls, _ in proofs}
    assert kinds["idle"] == "" and kinds["finding"] == kinds["found"] == kinds["promises"] == "robot"
    assert kinds["cups"] == kinds["guide"] == kinds["out"] == "not"  # never tried on the robot with real things
    assert all(text.startswith(("On the robot", "Not yet", "Timed on the robot")) for _, cls, text in proofs if cls)
    assert overlaps == {390: [], "390 wider": False, 360: [], "360 wider": False}


def test_the_public_demo_opens_on_a_front_door_with_one_thing_to_try_first(browser):
    """November 2: the Space opened on the TV's dashboard under a bar of six controls, the robot nowhere, and the most
    magical thing a visitor can do (Andy's eyes on their own things) behind "Explore every screen". Now a front door:
    Andy's face, one line, the shared card's numbers, and one bright action, Andy's eyes; the story a press away.
    Links that name a scene, ask, explore or ask for the story go straight there; Andy's own TV never shows it."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    seen = {}
    try:
        for width, height in ((1440, 900), (390, 844), (360, 740)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.add_init_script("window.HEYANDY_FIGURES = [['250 of 253', 'searches on the robot ended in a point']];")
            errors = []
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            page.goto(base)
            page.wait_for_selector("#welcome", timeout=10000)
            seen[width] = page.evaluate("""() => { const w = document.getElementById('welcome'), cta = w.querySelector('a.cta');
              const r = cta.getBoundingClientRect();
              return { title: w.querySelector('h1').textContent, cta: cta.getAttribute('href'), ctaAbove: r.bottom <= innerHeight,
                       tall: r.height, wide: document.documentElement.scrollWidth > innerWidth, figures: w.querySelectorAll('.proof li').length,
                       behind: [...document.body.children].filter(e => e.id !== 'welcome').every(e => e.inert),
                       storying: document.body.classList.contains('storying'), focused: document.activeElement === w } }""")
            page.keyboard.press("Tab")
            first = page.evaluate("document.activeElement.className")
            page.keyboard.press("Tab")
            seen[width]["tab"] = [first, page.evaluate("document.activeElement.className")]
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            seen[width]["after escape"] = page.evaluate("""() => [!!document.getElementById('welcome'), document.body.classList.contains('storying'),
                                                              [...document.body.children].some(e => e.inert)]""")
            seen[width]["errors"] = errors
            page.close()
        for query in ("?story", "?scene=found", "?explore", "?ask=where are my glasses"):
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(base + query)
            page.wait_for_timeout(1200)
            seen[query] = page.evaluate("!!document.getElementById('welcome')")
            page.close()
        page = browser.new_page(viewport={"width": 1440, "height": 900})  # built with the robot filmed: the robot first
        page.add_init_script("window.HEYANDY_CLIP = 'robot.mp4';")
        page.goto(base)
        page.wait_for_selector("#welcome", timeout=10000)
        seen["clip"] = page.evaluate("[!!document.querySelector('#welcome .robot video'), !!document.querySelector('#welcome .face')]")
        page.close()
    finally:
        server.shutdown()
    for width in (1440, 390, 360):
        s = seen[width]
        assert s["errors"] == [] and s["title"] == "Lost something? Andy points at it." and s["cta"] == "eyes.html?find"
        assert s["ctaAbove"] and s["tall"] >= 44 and not s["wide"] and s["figures"] == 1  # the action on the first screen
        assert s["behind"] and not s["storying"] and s["focused"] and s["tab"] == ["langbtn", "cta"]  # the top, then the action
        assert s["after escape"] == [False, True, False]  # Escape: into the story, nothing left inert
    assert not any(seen[q] for q in ("?story", "?scene=found", "?explore", "?ask=where are my glasses"))
    assert seen["clip"] == [True, False]


def test_andy_introduces_itself_in_its_own_voice_in_the_bubbles_language(browser):
    """The front door's face is a button, and so is "Hear Andy": Andy's own voice (SeamlessM4T v2) saying its hand-written
    introduction in the bubble's language; the bubble shows those words while it speaks, then goes on."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script("""window.HEYANDY_ASKS = [['es', '¿Dónde están mis gafas?']];
          window.HEYANDY_VOICES = { en: { text: "I'm Andy, an AI robot.", file: 'voice/en.mp3' },
                                    es: { text: 'Soy Andy, un robot con inteligencia artificial.', file: 'voice/es.mp3' } };""")
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        page.wait_for_selector("#welcome .hear", timeout=10000)
        page.wait_for_function("document.querySelector('#welcome .bubble small').textContent === 'Español'", timeout=8000)
        label = page.get_attribute("#welcome .hear", "aria-label")
        face = page.get_attribute("#welcome button.talk", "aria-label")
        page.click("#welcome button.talk")
        speaking = page.evaluate("""() => [document.querySelector('#welcome .bubble q').textContent,
                                          document.querySelector('#welcome .bubble small').textContent,
                                          document.querySelector('#welcome .bubble').classList.contains('own')]""")
        page.wait_for_function("!document.querySelector('#welcome .bubble').classList.contains('own')", timeout=8000)
        page.keyboard.press("Escape")
        page.close()
    finally:
        server.shutdown()
    assert label == face == "Hear Andy introduce itself, in Español"
    assert speaking == ["Soy Andy, un robot con inteligencia artificial.", "Español · Andy's own voice", True]


def test_andys_own_tv_never_shows_the_front_door(browser):
    server = serve(ScreenState(), port=0)  # the robot's TV: no demo scenes
    try:
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        page.wait_for_timeout(1500)
        shown = page.evaluate("!!document.getElementById('welcome')")
        page.close()
    finally:
        server.shutdown()
    assert shown is False


def test_the_front_door_speaks_the_visitors_language_and_lets_them_choose_another(browser):
    """November 2, the founder: "if we have multiple languages, do we need an indicator with a country flag?" No flag (a
    language isn't a country): each of Andy's fifteen in its own name and script. A browser that speaks one of them
    gets it on the front door (the bubble, Andy's voice, the story's "Your language" chapter); a globe button chooses."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    init = """window.HEYANDY_ASKS = [['ko', '내 안경 어디 있어?'], ['fr', 'Où sont mes lunettes ?']];
              window.HEYANDY_VOICES = { en: { text: "I'm Andy, an AI robot.", file: 'voice/en.mp3' },
                                        ko: { text: '저는 앤디, 인공지능 로봇이에요.', file: 'voice/ko.mp3' } };"""
    try:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
        page = ctx.new_page()
        page.add_init_script(init)
        page.goto(base)
        page.wait_for_selector("#welcome .langbtn", timeout=10000)
        korean = page.evaluate("""() => [document.querySelector('#welcome .langbtn').textContent, document.querySelector('#welcome .bubble q').textContent,
                                        document.querySelector('#welcome .hear').getAttribute('aria-label'), document.querySelector('#welcome .tip').textContent,
                                        STORY.find(c => c[2] === 'Your language')[0]]""")
        page.click("#welcome .langbtn")
        listed = page.eval_on_selector_all("#w-langs button", "els => els.map(e => [e.lang, e.childNodes[0].textContent, e.getAttribute('aria-pressed')])")
        flags = page.evaluate("/[\\u{1F1E6}-\\u{1F1FF}]/u.test(document.getElementById('w-langs').textContent)")
        page.keyboard.press("Escape")  # closes the list, not the front door
        still_open = page.evaluate("[!!document.getElementById('welcome'), document.getElementById('w-langs').hidden]")
        page.click("#welcome .langbtn")
        page.click("#w-langs button[lang=fr]")
        french = page.evaluate("""() => [document.querySelector('#welcome .langbtn').textContent, document.querySelector('#welcome .bubble q').textContent,
                                        localStorage.getItem('andy-lang'), STORY.find(c => c[2] === 'Your language')[0]]""")
        page.reload()
        page.wait_for_selector("#welcome .langbtn", timeout=10000)
        remembered = page.text_content("#welcome .langbtn")
        ctx.close()
        english = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US").new_page()
        english.add_init_script(init)
        english.goto(base)
        english.wait_for_selector("#welcome .langbtn", timeout=10000)
        plain = [english.text_content("#welcome .langbtn"), english.evaluate("STORY.find(c => c[2] === 'Your language')[0]")]
        english.context.close()
    finally:
        server.shutdown()
    assert korean == ["한국어", "내 안경 어디 있어?", "Hear Andy introduce itself, in 한국어", "Andy speaks 한국어 too: tap Andy to hear it", "in-ko"]
    assert len(listed) == 15 and ["ko", "한국어", "true"] in listed and ["uk", "Українська", "false"] in listed and not flags
    assert still_open == [True, True]
    assert french == ["Français", "Où sont mes lunettes ?", "fr", "in-fr"] and remembered == "Français"
    assert plain == ["English", "mandarin"]  # English: the story's chapter as it was, the bubble going round


def test_the_story_is_told_in_andys_voice_and_a_press_turns_it_off(browser):
    """The public demo's story, told chapter by chapter in Andy's own voice when the Space is built with it: on from the
    press that started the story, each chapter as long as its words if they're longer, off with a press; and a browser
    that won't play sound unasked (a link straight to ?story) offers it instead."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    init = """window.HEYANDY_NARRATION = { "Meet Andy": { text: "Hi, I'm Andy.", file: "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=", seconds: 9.5 },
                                         "You ask": { text: "You ask.", file: "voice/none.mp3", seconds: 2 } };"""
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(init)
        page.goto(base)
        page.wait_for_selector("#welcome", timeout=10000)
        page.click("text=Watch Andy's story")
        page.wait_for_selector("#story .voice", timeout=5000)
        first = page.evaluate("[chapterSeconds(0), STORY[0][1], chapterSeconds(1), document.querySelector('#story .voice').getAttribute('aria-pressed')]")
        page.click("#story .voice")
        off = page.evaluate("[narrate, chapterSeconds(0), document.querySelector('#story .voice').textContent]")
        page.close()
        direct = browser.new_page(viewport={"width": 1440, "height": 900})
        direct.add_init_script(init)
        direct.goto(base + "?story")
        direct.wait_for_function("document.querySelector('#story .voice') && document.querySelector('#story .voice').getAttribute('aria-pressed') === 'false'", timeout=5000)
        asked = direct.text_content("#story .voice")
        direct.close()
    finally:
        server.shutdown()
    assert first[0] == pytest.approx(10.4) and first[1] == 6 and first[2] == 6 and first[3] == "true"  # longer words, longer chapter
    assert off == [False, 6, "Andy's voice: off"]
    assert asked == "▶ Hear Andy tell it"


def test_a_scene_asked_for_or_picked_is_said_in_andys_voice_and_the_story_keeps_its_own(browser):
    """The public demo's scenes, each said in Andy's own voice when the visitor asks or picks one: a find says "Let me
    look." and then the find; never while the scenes go round by themselves; off with "Andy's voice"; the story keeps
    its own telling."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    init = """window.HEYANDY_SCENE_VOICE = Object.fromEntries(["found", "finding", "memory", "help", "room"].map(n => [n, { text: n, file: `voice/scene-${n}.mp3` }]));
              window.played = []; const A = window.Audio; window.Audio = function (src) { window.played.push(String(src).split('/').pop()); return new A(src); };"""
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(init)
        page.goto(base + "?explore")
        page.wait_for_selector("#demo .voice", timeout=10000)
        page.wait_for_timeout(1500)
        idle = page.evaluate("window.played.length")  # going round by themselves: nothing said
        page.click("#demo button:text('Memory')")
        page.fill("#demo form.ask input", "where are my keys?")
        page.press("#demo form.ask input", "Enter")
        page.wait_for_function("window.played.includes('scene-found.mp3')", timeout=6000)
        asked = page.evaluate("window.played")
        page.click("#demo .voice")
        page.click("#demo button:text('Memory')")
        off = page.evaluate("[window.played.length, document.querySelector('#demo .voice').textContent]")
        page.close()
    finally:
        server.shutdown()
    assert idle == 0
    assert asked == ["scene-memory.mp3", "scene-finding.mp3", "scene-found.mp3"]
    assert off == [3, "Andy's voice: off"]


def test_the_story_ends_with_andy_saying_its_your_turn_and_three_ways_on(browser):
    """November 2: the story's end card offered thirteen things at once, Andy gone and nothing to share, its figures
    written into the page. Now "Your turn": Andy's face and its closing words (said in its voice when the story was told
    in it), the figures read from the scorecards, three ways on (Andy's eyes first), and a link to share."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    init = """window.HEYANDY_FIGURES = [['250 of 253', 'searches on the robot ended in a point']];
              window.HEYANDY_NARRATION = { "Your turn": { text: "That's me.", file: "voice/story-11.mp3", seconds: 3.3 } };
              window.played = []; const A = window.Audio; window.Audio = function (src) { window.played.push(String(src).split('/').pop()); return new A(src); };"""
    try:
        seen = {}
        for width, height in ((1440, 900), (1366, 680), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.add_init_script(init)
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/?story")
            page.wait_for_selector("#story", timeout=10000)
            page.evaluate("endCard()")
            page.wait_for_selector("#end .way.main", timeout=3000)
            seen[width] = page.evaluate("""() => { const e = document.getElementById('end'), main = e.querySelector('.way.main');
              e.scrollTo(0, 0);
              return { bubble: e.querySelector('.bubble').textContent, ways: [...e.querySelectorAll('.way b')].map(b => b.textContent),
                       main: main.getAttribute('href'), figs: [...e.querySelectorAll('.figs b')].map(b => b.textContent),
                       share: !![...e.querySelectorAll('.go button')].find(b => b.textContent === 'Share Andy'),
                       top: e.querySelector('.sig').getBoundingClientRect().top, played: window.played.slice(-1),
                       gear: getComputedStyle(document.getElementById('gear')).display, wide: document.documentElement.scrollWidth > innerWidth } }""")
            page.hover("#end .way.main")
            seen[width]["hover"] = page.evaluate("getComputedStyle(document.querySelector('#end .way.main')).backgroundColor")
            page.close()
    finally:
        server.shutdown()
    for width, s in seen.items():
        assert s["bubble"] == "That's me. Now it's your turn: show me something of yours."
        assert s["ways"][:2] == ["Find something of yours →", "Ask Andy"] and s["main"] == "eyes.html?find"
        assert s["figs"] == ["250 of 253"] and s["share"] and s["gear"] == "none" and not s["wide"]
        assert s["top"] >= 0, width  # its top on the screen, even when it's taller (it scrolls)
        assert s["hover"] == "rgb(255, 220, 138)"  # the main way stays gold under a mouse
        assert s["played"] == ["story-11.mp3"]  # Andy's closing words, in its voice


def test_the_story_is_told_in_the_visitors_language_and_english_is_a_press_away(browser):
    """November 2: the front door greeted a visitor in their own language, and then told the story in English. Now, when
    the Space is built with it, the story is told in the language chosen at the front door (or the browser's own): Andy's
    words in that language's voice, as subtitles, the measurements under them as measured, a line saying who
    translated it, Andy's closing words in it too, and English a press away; a language not built stays English."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    base = f"http://127.0.0.1:{server.server_address[1]}/?story"
    built = """window.HEYANDY_NARRATION = { "Meet Andy": { text: "Hi, I'm Andy.", file: "voice/story-01.mp3", seconds: 5 },
                                         "Your turn": { text: "That's me.", file: "voice/story-11.mp3", seconds: 3 } };
               window.HEYANDY_NARRATION_IN = { ar: { "Meet Andy": { title: "تعرّف على Andy", text: "مرحبًا، أنا آندي.", file: "voice/story-ar-01.mp3", seconds: 5 },
                                                     "Your turn": { title: "", text: "هذا أنا.", file: "voice/story-ar-11.mp3", seconds: 3 } } };
               window.played = []; const A = window.Audio; window.Audio = function (src) { window.played.push(String(src).split('/').pop()); return new A(src); };"""
    shown = """() => { const t = document.querySelector('#story .text'), h = t.querySelector('h2'), p = t.querySelector('p');
      return { title: h.textContent, line: p.textContent, lang: [h.lang, p.lang, p.dir], proof: !!t.querySelector('.proof'),
               mt: t.querySelector('.mt')?.textContent || '', tongue: document.querySelector('#story .tongue')?.textContent || null,
               file: told(0).file.split('/').pop() } }"""
    try:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.add_init_script("try { localStorage.setItem('andy-lang', 'ar'); } catch (e) {}\n" + built)
        page.goto(base)
        page.wait_for_selector("#story .tongue", timeout=10000)
        arabic = page.evaluate(shown)
        page.click("#story .tongue")
        english = page.evaluate(shown)
        page.click("#story .tongue")
        back = page.evaluate(shown)
        page.evaluate("endCard()")
        page.wait_for_selector("#end .bubble", timeout=3000)
        ending = page.evaluate("[document.querySelector('#end .bubble').textContent, document.querySelector('#end .bubble').lang, window.played.slice(-1)[0]]")
        wide = page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.close()
        plain = browser.new_page(viewport={"width": 1440, "height": 900})
        plain.add_init_script("try { localStorage.setItem('andy-lang', 'ko'); } catch (e) {}\n" + built)  # Korean not built
        plain.goto(base)
        plain.wait_for_selector("#story .text h2", timeout=10000)
        korean = plain.evaluate(shown)
        plain.close()
    finally:
        server.shutdown()
    assert arabic["title"] == "تعرّف على Andy" and arabic["line"] == "مرحبًا، أنا آندي." and arabic["lang"] == ["ar", "ar", "auto"]
    assert arabic["file"] == "story-ar-01.mp3" and arabic["tongue"] == "In English"
    assert "translated by Muse Glimmer" in arabic["mt"] and "not yet by a native speaker" in arabic["mt"]
    assert english["title"] == "Meet Andy" and english["file"] == "story-01.mp3" and english["tongue"] == "العربية" and english["mt"] == ""
    assert back["title"] == arabic["title"] and back["tongue"] == "In English"
    assert ending == ["هذا أنا.", "ar", "story-ar-11.mp3"] and not wide  # Andy's closing words in the story's language
    assert korean["title"] == "Meet Andy" and korean["tongue"] is None and korean["file"] == "story-01.mp3"


def test_the_front_door_says_which_language_the_story_is_told_in(browser):
    """A language chosen at the front door (its globe) tells the story in it, where the Space is built with it, and the
    story's button says so; one not built leaves the button as it was."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})  # the public demo
    try:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.add_init_script("""window.HEYANDY_NARRATION_IN = { ko: { "Meet Andy": { title: "앤디를 만나 보세요", text: "안녕하세요.", file: "voice/story-ko-01.mp3", seconds: 5 } } };""")
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        page.wait_for_selector("#welcome .langbtn", timeout=10000)
        before = page.text_content("#welcome .more button")
        page.click("#welcome .langbtn")
        page.click("#welcome button[lang=ko]")
        korean = page.evaluate("[document.querySelector('#welcome .more button').textContent, document.querySelector('#welcome .more button .in').lang]")
        page.click("#welcome .langbtn")
        page.click("#welcome button[lang=fr]")
        french = page.text_content("#welcome .more button")
        page.close()
    finally:
        server.shutdown()
    assert before.startswith("Watch Andy's story · ") and before.endswith(" min")
    assert korean == [before + " · 한국어", "ko"] and french == before
    long = browser.new_page(viewport={"width": 390, "height": 844})  # told in Korean, the story is as long as its words
    try:
        server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
        long.add_init_script("""try { localStorage.setItem('andy-lang', 'ko'); } catch (e) {}
          window.HEYANDY_NARRATION_IN = { ko: { "You ask": { title: "", text: "", file: "x.mp3", seconds: 60 } } };""")
        long.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        long.wait_for_selector("#welcome .more button .in", timeout=10000)
        assert long.text_content("#welcome .more button") == "Watch Andy's story · 2 min · 한국어"
    finally:
        long.close()
        server.shutdown()


def test_the_map_of_watched_things_never_prints_one_name_over_another(browser):
    """November 3, on the robot's TV: the cup, the keys and the glasses seen close together, and "keys" printed through
    "glasses". Each name now keeps clear of those already placed."""
    server = serve(ScreenState(), port=0)
    try:
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        page.wait_for_timeout(800)
        boxes = page.evaluate("""() => {
          const places = [{label: "cup", yaw: -8, pitch: -20, metres: 1.2, ago_s: 5},
                          {label: "keys", yaw: -12, pitch: -22, metres: 1.15, ago_s: 600},
                          {label: "glasses", yaw: -10, pitch: -21, metres: 1.18, ago_s: 5},
                          {label: "remote", yaw: 60, pitch: -10, metres: 2.0, ago_s: 50}];
          const svg = dial(places, false); document.body.append(svg); untangle(svg);
          return [...svg.querySelectorAll("text.name")].map(t => { const b = t.getBBox(); return [t.textContent, b.x, b.y, b.x + b.width, b.y + b.height]; });
        }""")
        page.close()
    finally:
        server.shutdown()
    assert [b[0] for b in boxes] == ["cup", "keys", "glasses", "remote"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            overlap = a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]
            assert not overlap, (a, b)


def test_the_help_panel_starts_below_the_demos_band_and_scrolls_when_taller_than_the_screen(browser):
    """November 3, the screen audit: "What can I ask Andy?" was taller than a TV and centred, so it was cut at both
    ends, and in the public demo its title was under the band of buttons. It now starts below the band, sits centred
    across, and scrolls; on a phone as well."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    seen = {}
    try:
        for size in ((1920, 1080), (390, 844)):
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/?ask=what%20can%20you%20do")
            page.wait_for_timeout(2500)
            seen[size] = page.evaluate("""() => {
              const help = document.getElementById("help"), panel = help.querySelector(".panel").getBoundingClientRect();
              const band = document.querySelector("nav").getBoundingClientRect();
              return {shown: !help.hidden, title: help.querySelector("h1").getBoundingClientRect().top, band: band.bottom,
                      left: panel.left, right: innerWidth - panel.right, scrolls: help.scrollHeight > help.clientHeight};
            }""")
            page.close()
    finally:
        server.shutdown()
    for size, s in seen.items():
        assert s["shown"] and s["title"] > s["band"], (size, s)  # the title isn't under the band
        assert abs(s["left"] - s["right"]) < 2, (size, s)  # centred across
        assert s["scrolls"], (size, s)  # taller than the screen: it scrolls, nothing is cut off


def test_what_a_judge_types_plays_the_scene_that_answers_it(browser):
    """November 3, a judge-style review of the public demo: "I fell and I can't get up" played the mug found (911 only in
    small grey type), "what's the weather tomorrow?" a web page on banana bread, "tell me a joke" the weather, and the
    Mandarin button asked for the glasses over a scene that finds a cup."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import PLAYED, show

    from heyandy_meta.companion.safety import EMERGENCY_REPLY

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in PLAYED})
    got = {}

    def typed(page_):
        got.update(page_.evaluate("""() => ({
          fell: route("I fell and I can't get up"), weather: route("what's the weather tomorrow?"), rain: route("will it rain?"),
          radar: route("show me the weather radar on the TV"), joke: route("tell me a joke"), time: route("what time is it?"),
          mug: route("where's my mug?"), zh: ASK_TRY.find((x) => /[\u4e00-\u9fff]/.test(x)) })"""))
        page_.evaluate("() => ask(\"I fell and I can't get up\")")
        page_.wait_for_timeout(1500)
        got["caption"] = page_.evaluate("() => document.getElementById('captions').innerText")
        page_.evaluate("() => ask('tell me a joke')")
        got["joke note"] = page_.evaluate("() => asked.note")

    try:
        assert errors_on(browser, f"http://127.0.0.1:{server.server_address[1]}/?explore", 1500, typed) == []
    finally:
        server.shutdown()
    assert got["fell"] == "emergency" and got["caption"].startswith(EMERGENCY_REPLY) and "phone" in got["caption"]
    assert got["weather"] == got["rain"] == "answer" and got["radar"] == "web" and got["mug"] == "find"
    assert got["joke"] == got["time"] == "help" and "answers that out loud" in got["joke note"]
    assert "杯子" in got["zh"]  # the Mandarin scene finds a cup (我看到您的蓝色杯子), so its button asks for one


def test_the_story_band_never_covers_the_tv_on_a_desktop(browser):
    """November 3, a judge-style review: at a fixed 0.85 the story's band covered the TV's day and Andy's state on a
    1080p screen. The TV is now sized under each chapter's band, measured."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    gaps = {}
    try:
        for size in ((1920, 1080), (1366, 768)):
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/?story")
            page.wait_for_function("() => typeof STORY !== 'undefined'", timeout=10000)
            for i in range(page.evaluate("() => STORY.length")):
                page.evaluate(f"() => {{ if (!story) startStory(); story.paused = true; go({i}); }}")
                page.wait_for_timeout(500)
                gaps[(size, i)] = page.evaluate("() => document.querySelector('.stage').getBoundingClientRect().top"
                                                " - document.getElementById('story').getBoundingClientRect().bottom")
            page.close()
    finally:
        server.shutdown()
    assert gaps and all(g >= 0 for g in gaps.values()), {k: v for k, v in gaps.items() if v < 0}
