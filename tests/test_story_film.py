"""Andy's story as a film (scripts/story_film.py): the public demo's story drawn frame by frame under a clock the script
turns, Andy's words laid in where the page started them, its buttons hidden and where to try it said."""
import functools
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import story_film  # noqa: E402
from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

# Every chapter (and the end card's "Your turn") told in a second, in English and in Arabic, whatever its title.
VOICES = """(() => {
  const told = (where) => new Proxy({}, { get: (_, k) => typeof k === "string" && k !== "then"
    ? { title: k + " (" + where + ")", text: "said: " + k, file: "voice/" + where + "-" + k.replace(/\\W+/g, "-") + ".mp3", seconds: 1 }
    : undefined });
  window.HEYANDY_NARRATION = told("en");
  window.HEYANDY_NARRATION_IN = { ar: told("ar") };
})();"""
FPS = 2  # Andy's words are timed by the page's clock, not by the frames
LOOK = """({ chapters: STORY.map(s => s[1]), titles: STORY.map(s => s[2]),
           nav: getComputedStyle(document.querySelector("#story nav") || document.body).display,
           credit: [...document.querySelectorAll(".film-credit")].map(c => c.textContent),
           end: !!document.querySelector("#end .go .film-credit") })"""


@pytest.fixture()
def page_url():
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    yield f"http://127.0.0.1:{server.server_address[1]}/?story"
    server.shutdown()


def _draw(url, lang, monkeypatch, **kw):
    pytest.importorskip("playwright")
    monkeypatch.setitem(story_film.SHAPES, "small", (640, 360, 1))
    frames = []
    try:
        told = story_film.draw(url, frames.append, lang, "small", fps=FPS, length=lambda src: 1.0, init=VOICES,
                               look=LOOK, before="STORY.forEach(s => { s[1] = 1; })", **kw)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - no browser here: skip
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no Chromium for Playwright: {e}")
        raise
    return told, frames


def test_the_story_is_drawn_frame_by_frame_and_andy_speaks_where_the_page_said_it(page_url, monkeypatch):
    told, frames = _draw(page_url, "ar", monkeypatch)
    first, last = told["looked"]
    chapters = first["chapters"]
    # each chapter lasts its own seconds or, longer here, its voice (a second) and a breath: Andy starts each as it begins
    secs = [max(c, 1.0 + 0.9) for c in chapters]
    starts = [sum(secs[:i]) for i in range(len(secs))]
    said = told["said"]
    names = [re.sub(r"\W+", "-", t) for t in [*first["titles"], "Your turn"]]
    assert [s["src"] for s in said] == [f"voice/ar-{n}.mp3" for n in names]
    for i, start in enumerate(starts):
        assert abs(said[i]["at"] - start) < 0.02 * (i + 1) + 0.02, (i, said[i], start)
        assert said[i]["until"] is not None and said[i]["until"] >= said[i]["at"]  # stopped as the next chapter began
    closing = said[-1]["at"]
    assert abs(closing - sum(secs)) < 0.3 and said[-1]["until"] is None
    # the end card held for the closing words (a second here) and a breath; every frame drawn
    assert closing + 1.0 + story_film.HOLD_S <= told["seconds"] <= closing + 1.0 + story_film.HOLD_S + 2 / FPS + 0.05
    assert len(frames) == told["frames"] == round(told["seconds"] * FPS)
    assert all(f[:2] == b"\xff\xd8" for f in frames)  # JPEGs, on their way to the encoder
    # what the screen said, in the story's language, chapter by chapter, then Andy's closing words: the subtitles
    assert [c["text"].split("\n")[0] for c in told["cues"][:3]] == [f"{t} (ar)" for t in first["titles"][:3]]
    assert told["cues"][-1]["text"] == "said: Your turn" and told["cues"][-1]["until"] == told["seconds"]
    # a film can't be pressed: the story's buttons hidden, and where to try it said, in the story and on the end card
    assert first["nav"] == "none" and first["credit"] == ["".join(story_film.CREDIT)]
    assert last["end"] and last["credit"] == ["".join(story_film.CREDIT)]


def test_a_language_the_space_doesnt_tell_the_story_in_is_refused(page_url, monkeypatch):
    with pytest.raises(SystemExit, match="doesn't tell the story in 'ko'"):
        _draw(page_url, "ko", monkeypatch)


def test_the_sound_is_laid_where_the_page_said_it_and_cut_where_it_stopped():
    said = [{"src": "a.mp3", "at": 0.5, "until": 1.2}, {"src": "b.mp3", "at": 2.0, "until": None}]
    graph = story_film.sound_graph(said, 3.0, lambda src: {"a.mp3": 2.0, "b.mp3": 2.0}[src])
    assert "[1:a]atrim=0:0.700," in graph and "adelay=500:all=1[s0]" in graph  # stopped at 1.2 s: 0.7 s of it
    assert "[2:a]atrim=0:1.000," in graph and "adelay=2000:all=1[s1]" in graph  # the film ends at 3 s
    assert "amix=inputs=2:normalize=0" in graph and "atrim=0:3.000[m]" in graph and "loudnorm=I=-16" in graph
    assert story_film.sound_graph([], 2.0, len).startswith("anullsrc=r=48000:cl=stereo,atrim=0:2.000[m]")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("no ffmpeg here")
    cmd = [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x36:d=3:r=30"]
    for f in ("440", "660"):
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration=2"]
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-f", "null", "-"]
    assert subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def test_the_subtitles_are_each_chapters_words_for_as_long_as_its_on_screen():
    out = story_film.srt([{"at": 0.0, "until": 6.05, "text": "Meet Andy\nA tabletop robot"},
                          {"at": 76.6, "until": 3725.5, "text": "That's me."}])
    assert out == ("1\n00:00:00,000 --> 00:00:06,050\nMeet Andy\nA tabletop robot\n\n"
                   "2\n00:01:16,600 --> 01:02:05,500\nThat's me.\n")


def test_its_films_and_their_frames_stay_out_of_the_repository():
    ignored = subprocess.run(["git", "check-ignore", "film/story-en-wide.mp4"], cwd=ROOT, capture_output=True, text=True)
    assert ignored.returncode == 0
    assert story_film.FILM == ROOT / "film" and set(story_film.SHAPES) >= {"wide", "vertical"}
    for w, h, scale in (story_film.SHAPES["wide"], story_film.SHAPES["vertical"]):
        assert min(w, h) * scale >= 1080  # each 1080 lines or more
