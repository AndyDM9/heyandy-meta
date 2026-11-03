"""Andy's story, as a film: the public demo's story drawn frame by frame and told in Andy's own voice, in any of its
fifteen languages. For the video (a piece in make_film.py's cut, whatever filming brings), and for sharing.

The story on the Space (index.html?story) is the demo's own: its scenes, each chapter's words and what it rests on, and
Andy telling it (scripts/front_door_voice.py), in the visitor's language. This draws it as it is, from the built Space
(dist/space-static, scripts/build_static_space.py), under a clock this script turns: each frame is exactly its moment
(the page's timers, and every animation, set to it; then a screenshot), not screen-recorded, so it's sharp and doesn't
skip, however long a frame takes to draw. Andy's words are laid in where the page started them, from the same files the
page plays. Its buttons are hidden (a film can't be pressed) and a line says where to try it. The scenes are the
demo's drawings, never a camera's picture. Nothing is uploaded: the films go in film/ (git-ignored), each with its
subtitles (.srt, for a site's captions) and what it was made from (.json: the page's and each voice file's SHA-256).

    uv run python scripts/build_static_space.py           # first: the Space as it'll be published
    uv run python scripts/story_film.py                   # -> film/story-en-wide.mp4 (1920 by 1080), .srt, .json
    uv run python scripts/story_film.py --lang ko ar --shape vertical   # Korean and Arabic, 1080 by 1920, for a phone
    uv run python scripts/story_film.py --lang all        # all fifteen

A piece in the film's cut as it is: {"path": "film/story-en-wide.mp4"} in film/cut.json (make_film.py cut).
"""
import argparse
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILT = ROOT / "dist" / "space-static"
FILM = ROOT / "film"
FFMPEG = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FPS = 30
QUALITY = 92  # each frame's JPEG on its way to the encoder
# (the page's width and height in CSS pixels, its pixel ratio): a TV, and a phone held upright, each 1080 lines or more
SHAPES = {"wide": (1920, 1080, 1), "vertical": (540, 960, 2)}
START = datetime(2026, 11, 4, 10, 30)  # the page's clock: the TV's day and time, and its reminder's, are read from it
HOLD_S = 2.5  # the end card stays this long after Andy's closing words
MOST_S = 300.0  # a story that hasn't ended by then has gone wrong
CREDIT = ("Try it yourself", "huggingface.co/spaces/heyandy-ai/andy")
# The browser's language for each of Andy's: whatever else on the page follows the visitor's language follows the film's.
LOCALES = {"en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "it": "it-IT", "pt": "pt-BR", "zh": "zh-CN",
           "ja": "ja-JP", "ko": "ko-KR", "hi": "hi-IN", "ar": "ar-SA", "ru": "ru-RU", "uk": "uk-UA", "vi": "vi-VN",
           "tl": "fil-PH"}

# In the page before its own script: Andy's voice played into a list (the file, and when it started and stopped, by the
# page's clock), not out loud; and __frame(), which sets every animation (and a filmed clip, if the Space has one) to
# the clock's moment and says what's on the screen.
PAGE = r"""(() => {
  const said = window.__said = [];
  window.Audio = class {
    constructor(src) { this.src = src || ""; this.paused = true; this.currentTime = 0; }
    play() { this.paused = false; said.push({ src: this.src, at: Date.now(), until: null }); this._i = said.length - 1; return Promise.resolve(); }
    pause() { if (!this.paused && this._i !== undefined && said[this._i].until === null) said[this._i].until = Date.now(); this.paused = true; }
    addEventListener() {} removeEventListener() {} load() {}
  };
  const born = new WeakMap();
  window.__film = (lead, where) => {
    const s = document.createElement("style");
    s.textContent = `#story nav, #story .tongue { display: none !important; }
      .film-credit { flex: none; text-align: right; font: 600 1.15rem/1.35 "Atkinson Next", sans-serif; color: rgba(245, 243, 239, 0.8); }
      .film-credit b { display: block; color: var(--outline); font-size: 1.3rem; }
      #end .go .film-credit { margin-left: auto; align-self: center; }
      @media (max-aspect-ratio: 1/1) { .film-credit { width: 100%; text-align: left; font-size: 3.6vw; } .film-credit b { font-size: 4vw; }
        #end .go .film-credit { margin-left: 0; }
        body.storying .stage > header, body.storying .stage .side { display: none; } }`;
    document.head.append(s);
    window.__credit = () => { const c = document.createElement("div"); c.className = "film-credit";
      const b = document.createElement("b"); b.textContent = lead; c.append(b, where); return c; };
  };
  window.__frame = async () => {
    const now = Date.now();
    for (const a of document.getAnimations()) { if (!born.has(a)) { born.set(a, now); a.pause(); } a.currentTime = now - born.get(a); }
    for (const v of document.querySelectorAll("video")) {
      if (!born.has(v)) { born.set(v, now); v.pause(); v.autoplay = false; }
      if (v.readyState < 1) continue;
      const t = ((now - born.get(v)) / 1000) % (v.duration || Infinity);
      if (Math.abs(v.currentTime - t) > 0.001) await new Promise(r => { v.addEventListener("seeked", r, { once: true }); v.currentTime = t; });
    }
    const row = document.querySelector("#story .row"), end = document.querySelector("#end .go");
    for (const box of [row, end]) if (box && window.__credit && !box.querySelector(".film-credit")) box.append(window.__credit());
    const h = document.querySelector("#story .text h2"), p = document.querySelector("#story .text p"), b = document.querySelector("#end .bubble");
    return { text: h ? `${h.textContent}\n${p ? p.textContent : ""}` : (b ? b.textContent : ""), end: !!b, said: said.length };
  };
})();"""


def offered() -> list[str]:
    """English and each language the story is told in (story-in.json's offered ones, as the Space is built with)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_static_space import narration_in

    return ["en", *sorted(narration_in())]


def draw(url: str, frame, lang: str = "en", shape: str = "wide", fps: int = FPS, length=lambda src: 4.0,
         credit: tuple[str, str] | None = CREDIT, init: str = "", most_s: float = MOST_S, look: str = "",
         before: str = "") -> dict:
    """The story at url, from its first chapter to its end card, each frame (a JPEG's bytes) handed to frame() in turn.
    length(src) is how long a voice file is (for the end card's closing words). What it says: how many frames and
    seconds, what Andy said and when (seconds from the start), and what the screen said ("cues", for subtitles); and
    with look (a script), what it found on the first frame and the last ("looked"). before is a script run just before
    the story starts (a test's shorter chapters)."""
    from playwright.sync_api import sync_playwright

    width, height, scale = SHAPES[shape]
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale,
                                          locale=LOCALES.get(lang, "en-US"))
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.clock.install(time=START)
            page.add_init_script(PAGE)
            if init:
                page.add_init_script(init)
            page.goto(url, wait_until="load")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(800)  # real time, the clock still running: the scenes' pictures decoded
            page.clock.pause_at(START + timedelta(seconds=5))
            ok = page.evaluate("""([code, credit, before]) => {
                if (code !== "en" && !(window.HEYANDY_NARRATION_IN || {})[code]) return false;
                exploreAll(); toldChoice = code; window.__said.length = 0;
                if (credit) window.__film(credit[0], credit[1]);
                if (before) (0, eval)(before);
                startStory(); return true; }""", [lang, list(credit) if credit else None, before])
            if not ok:
                raise SystemExit(f"the Space at {url} doesn't tell the story in {lang!r}")
            t0 = page.evaluate("Date.now()")
            n, ticked, cues, ends, looked = 0, 0, [], None, []
            while True:
                state = page.evaluate("__frame()")
                frame(page.screenshot(type="jpeg", quality=QUALITY))
                if look and n == 0:
                    looked.append(page.evaluate(look))
                at = n / fps
                if not cues or cues[-1]["text"] != state["text"]:
                    cues.append({"at": at, "text": state["text"]})
                if state["end"] and ends is None:
                    said = page.evaluate("window.__said")
                    closing = [s for s in said if s["at"] >= t0 + at * 1000 - 1000 / fps]
                    ends = at + (length(closing[-1]["src"]) if closing else 0.0) + HOLD_S
                n += 1
                if ends is not None and n / fps >= ends:
                    break
                if n / fps > most_s:
                    raise SystemExit(f"the story hadn't ended after {most_s:.0f} s")
                due = round(n * 1000 / fps)
                page.clock.run_for(due - ticked)
                ticked = due
            if look:
                looked.append(page.evaluate(look))
            said = [{"src": s["src"], "at": round((s["at"] - t0) / 1000, 3),
                     "until": None if s["until"] is None else round((s["until"] - t0) / 1000, 3)}
                    for s in page.evaluate("window.__said")]
        finally:
            browser.close()
    if errors:
        raise SystemExit("the page stopped: " + "; ".join(errors[:3]))
    seconds = n / fps
    for i, c in enumerate(cues):
        c["until"] = cues[i + 1]["at"] if i + 1 < len(cues) else seconds
    return {"frames": n, "seconds": round(seconds, 3), "said": said, "cues": [c for c in cues if c["text"].strip()],
            "looked": looked}


def sound_graph(said: list[dict], seconds: float, length) -> str:
    """ffmpeg's filter for the sound: each voice file from where the page started it, cut where the page stopped it
    (input i+1 is said[i]; input 0 is the picture), mixed, padded with silence to the film's length, and its loudness
    evened out to -16 LUFS as video sites expect."""
    parts = []
    for i, s in enumerate(said):
        keep = min(length(s["src"]), (s["until"] - s["at"]) if s["until"] is not None else float("inf"),
                   seconds - s["at"])
        ms = max(0, round(s["at"] * 1000))
        parts.append(f"[{i + 1}:a]atrim=0:{keep:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"aformat=sample_fmts=fltp:channel_layouts=stereo,adelay={ms}:all=1[s{i}]")
    if said:
        parts.append("".join(f"[s{i}]" for i in range(len(said)))
                     + f"amix=inputs={len(said)}:normalize=0:dropout_transition=0,apad,atrim=0:{seconds:.3f}[m]")
    else:
        parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{seconds:.3f}[m]")
    parts.append("[m]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    return ";".join(parts)


def srt(cues: list[dict]) -> str:
    def stamp(s: float) -> str:
        ms = round(s * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    return "\n".join(f"{i}\n{stamp(c['at'])} --> {stamp(c['until'])}\n{c['text'].strip()}\n"
                     for i, c in enumerate(cues, 1))


def duration(path: Path) -> float:
    out = subprocess.run([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serving(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def make(lang: str, shape: str, built: Path = BUILT, out_dir: Path = FILM, fps: int = FPS) -> dict:
    """One film: the story in lang, its shape, from the built Space; the film, its subtitles and what it's made of."""
    if not (built / "index.html").exists():
        raise SystemExit(f"no Space built at {built}: run scripts/build_static_space.py first")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = out_dir / f"story-{lang}-{shape}"
    lengths = functools.cache(lambda src: duration(built / src))
    server = serving(built)
    began = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        picture = Path(tmp) / "picture.mp4"
        enc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
                                "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                str(picture)], stdin=subprocess.PIPE)
        try:
            told = draw(f"http://127.0.0.1:{server.server_address[1]}/index.html?story", enc.stdin.write, lang, shape,
                        fps, length=lengths)
        finally:
            enc.stdin.close()
            enc.wait()
            server.shutdown()
        if enc.returncode != 0:
            raise SystemExit("ffmpeg couldn't make the picture")
        cmd = [FFMPEG, "-v", "error", "-y", "-i", str(picture)]
        for s in told["said"]:
            cmd += ["-i", str(built / s["src"])]
        cmd += ["-filter_complex", sound_graph(told["said"], told["seconds"], lengths), "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(name.with_suffix(".mp4"))]
        subprocess.run(cmd, check=True)
    name.with_suffix(".srt").write_text(srt(told["cues"]))
    width, height, scale = SHAPES[shape]
    film = name.with_suffix(".mp4")
    made = {
        "what": "Andy's story, from the public demo (index.html?story), drawn frame by frame and told in Andy's own "
                "voice: scripts/story_film.py",
        "made": time.strftime("%Y-%m-%d %H:%M"),
        "language": lang,
        "translated": None if lang == "en" else
        "by Muse Glimmer, Andy's own translator; checked by machine, not yet by a native speaker",
        "shape": shape, "size": [width * scale, height * scale], "fps": fps, "frames": told["frames"],
        "seconds": told["seconds"], "drawn in s": round(time.time() - began, 1),
        "page": {"file": "dist/space-static/index.html", "sha256": sha256(built / "index.html")},
        "said": [{**s, "seconds": round(lengths(s["src"]), 3), "sha256": sha256(built / s["src"])} for s in told["said"]],
        "on screen": told["cues"],
        "film": {"file": str(film.relative_to(ROOT)) if film.is_relative_to(ROOT) else str(film),
                 "bytes": film.stat().st_size, "sha256": sha256(film)},
    }
    name.with_suffix(".json").write_text(json.dumps(made, indent=2, ensure_ascii=False) + "\n")
    return made


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lang", nargs="*", default=["en"], help="language codes, or 'all' (default: en)")
    ap.add_argument("--shape", nargs="*", default=["wide"], choices=sorted(SHAPES))
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--out", type=Path, default=FILM)
    args = ap.parse_args()
    langs = offered() if args.lang == ["all"] else args.lang
    for lang in langs:
        for shape in args.shape:
            m = make(lang, shape, out_dir=args.out, fps=args.fps)
            print(f"{m['film']['file']}: {lang}, {shape} {m['size'][0]}x{m['size'][1]}, {m['seconds']:.1f} s, "
                  f"{len(m['said'])} of Andy's lines, {m['film']['bytes'] / 1e6:.1f} MB (drawn in {m['drawn in s']:.0f} s)")


if __name__ == "__main__":
    main()
