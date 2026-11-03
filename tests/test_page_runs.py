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
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
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

    assert got["emergency"] == EMERGENCY_REPLY and EMERGENCY_REPLY in got["fell"] and got["fellScene"] == "found"
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
    from demo_screen import IN_LANGUAGE, SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    every = (*SCENES, *IN_LANGUAGE)
    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in every}, listed=list(SCENES))
    shown = {}
    try:
        pictured = {"found", "mandarin", "spanish", *IN_LANGUAGE}
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
            seen[width]["tab"] = page.evaluate("document.activeElement.className")
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
        assert s["errors"] == [] and s["title"] == "Lost something? Andy points at it." and s["cta"] == "eyes.html"
        assert s["ctaAbove"] and s["tall"] >= 44 and not s["wide"] and s["figures"] == 1  # the action on the first screen
        assert s["behind"] and not s["storying"] and s["focused"] and s["tab"] == "cta"
        assert s["after escape"] == [False, True, False]  # Escape: into the story, nothing left inert
    assert not any(seen[q] for q in ("?story", "?scene=found", "?explore", "?ask=where are my glasses"))
    assert seen["clip"] == [True, False]


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
