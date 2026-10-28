"""Before filming or a live demo: is everything Andy needs running and answering? About a minute; a list of checks.

    uv run python scripts/preflight.py            # everything on this computer
    uv run python scripts/preflight.py --cloud    # also one tiny Muse Spark call (a fraction of a cent)

Only drawn test pictures and synthesised speech are used: nothing from the camera or the microphone. It doesn't move
the robot (Andy's own service holds it); it reads Andy's recent log for errors instead.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("heyandy-glimmer", "heyandy-sam", "heyandy-voice", "heyandy-app")
results: list[tuple[bool, str, str]] = []


def check(name: str):
    def wrap(fn):
        start = time.monotonic()
        try:
            detail = fn() or ""
            ok = True
        except Exception as e:  # noqa: BLE001 - every failure is a line in the list, not a crash
            ok, detail = False, f"{type(e).__name__}: {e}"[:160]
        results.append((ok, name, f"{detail} ({time.monotonic() - start:.1f} s)"))
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {results[-1][2]}", flush=True)
        return fn
    return wrap


def drawn_mug() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (960, 540), (196, 184, 168))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 330, 960, 540), fill=(139, 104, 74))
    d.rounded_rectangle((440, 220, 540, 340), 12, fill=(38, 92, 170))
    d.arc((520, 250, 580, 310), 270, 90, fill=(38, 92, 170), width=12)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true", help="also make one tiny Muse Spark call")
    args = ap.parse_args()
    mug = drawn_mug()

    @check("services")
    def _():
        out = subprocess.run(["systemctl", "--user", "is-active", *SERVICES], capture_output=True, text=True).stdout.split()
        down = [s for s, state in zip(SERVICES, out) if state != "active"]
        if down:
            raise RuntimeError("not running: " + ", ".join(down) + " (systemctl --user start ...)")
        return "all four running"

    @check("Andy's log, last 10 minutes")
    def _():
        log = subprocess.run(["journalctl", "--user", "-u", "heyandy-app", "--since", "10 min ago", "--no-pager"],
                             capture_output=True, text=True).stdout
        bad = [line for line in log.splitlines() if "Traceback" in line or "a turn failed" in line]
        if bad:
            raise RuntimeError(f"{len(bad)} errors: {bad[-1][-120:]}")
        return "no errors"

    @check("TV page")
    def _():
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8765/state.json", timeout=5) as r:
            s = json.load(r)
        return f"answering; {'online' if s['online'] else 'OFFLINE'}; language {s.get('lang', 'en')}" + \
            ("; STAGED SCENE" if s.get("staged") else "")

    @check("SAM 3.1 finds a drawn mug")
    def _():
        from heyandy_meta.models.sam_local import LocalSam31

        sam = LocalSam31()
        masks = sam.find(mug, "mug")
        if not masks:
            raise RuntimeError("found nothing")
        vec = sam.embed(mug, masks[:1])[0]  # DINOv2, for "this is my mug"
        return f"score {masks[0].score:.2f}, {sam.last_latency_s:.2f} s; DINOv2 vector of {len(vec)}"

    @check("SAM 3.1 Object Multiplex tracks (the cup game)")
    def _():
        from heyandy_meta.models.sam_local import LocalSam31

        tracks = LocalSam31().track([mug, mug, mug], "mug")
        if not tracks or not tracks[0].end:
            raise RuntimeError("tracked nothing")
        return f"{len(tracks)} track(s) through 3 frames"

    @check("GPU memory for the cup game")
    def _():
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.strip().splitlines()
        used, total = (int(x) for x in out[1].split(",")[1:])
        free = (total - used) / 1024
        if free < 7:
            raise RuntimeError(f"GPU 1 has {free:.1f} GB free; tracking needs about 6.6 GB more")
        return f"GPU 1: {free:.1f} GB free"

    @check("voice: speak and hear, English and Spanish")
    def _():
        from heyandy_meta.voice.local import LocalVoice

        out = []
        for voice, lang, said in (("am_michael", "eng_Latn", "Where are my glasses?"),
                                  ("em_alex", "spa_Latn", "¿Dónde están mis gafas?")):
            v = LocalVoice(voice=voice)
            v.language = lang
            heard = v.transcribe(v.speak(said, rate=16000))
            if "gafas" not in heard.lower() and "glasses" not in heard.lower():
                raise RuntimeError(f"heard {heard!r} for {said!r}")
            out.append(repr(heard))
        return " / ".join(out)

    @check("Muse Glimmer answers")
    def _():
        from heyandy_meta.models import glimmer_fast

        a = glimmer_fast.answer("http://127.0.0.1:8080", [{"role": "user", "content": "Say OK and nothing else."}], 5)
        if not a:
            raise RuntimeError("empty answer")
        return repr(a)

    @check("web browser (for 'show me ... on the TV')")
    def _():
        from heyandy_meta.companion import web

        b = web.Browser(start="about:blank")
        try:
            b.screenshot()
            web.at_home("http://127.0.0.1:8765/")  # the home-network check itself
        finally:
            b.close()
        return "a clean headless browser starts"

    @check("cloud: key and spend")
    def _():
        env = Path.home() / ".config" / "heyandy-meta" / "env"
        if not env.exists():
            raise RuntimeError("no ~/.config/heyandy-meta/env: Andy runs on this computer only")
        if oct(env.stat().st_mode & 0o777) != "0o600":
            raise RuntimeError(f"{env} should be readable by you only (chmod 600)")
        keys = {line.split("=", 1)[0] for line in env.read_text().splitlines() if "=" in line}
        missing = {"MODEL_API_KEY", "HEYANDY_PAID_CALLS"} - keys
        if missing:
            raise RuntimeError("missing in the env file: " + ", ".join(sorted(missing)))
        from heyandy_meta.budget import Budget

        os.environ.setdefault("HEYANDY_PAID_CALLS", "1")
        spent = Budget(ledger=str(ROOT / "logs" / "spend.jsonl")).spent()
        return f"key set; spent ${spent:.2f} of the $140 cap" + ("" if "HEYANDY_HOME" in keys else "; no HEYANDY_HOME")

    if args.cloud:
        @check("Muse Spark answers")
        def _():
            from openai import OpenAI

            env = dict(line.split("=", 1) for line in (Path.home() / ".config/heyandy-meta/env").read_text().splitlines()
                       if "=" in line)
            c = OpenAI(base_url="https://api.meta.ai/v1", api_key=env["MODEL_API_KEY"].strip())
            r = c.chat.completions.create(model="muse-spark-1.3", reasoning_effort="minimal", max_tokens=200,
                                          messages=[{"role": "user", "content": "Say OK."}])
            return repr((r.choices[0].message.content or "").strip()[:20])

    failed = [name for ok, name, _ in results if not ok]
    print("\n" + ("READY: everything answered." if not failed else f"NOT READY: {len(failed)} to fix: " + ", ".join(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
