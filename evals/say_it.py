"""Say it: the public demo's microphone (screen/page.html, "🎙" in Ask Andy). Meta's wav2vec 2.0 base hears in the
browser; the things people say to the demo are scored against what it heard (CTC), and taken when one clearly fits
best, else the free transcript with near-miss words snapped to the demo's own.

Speech made by two of Meta's voices on this computer (SeamlessM4T v2, Andy's; MMS-TTS English), so it isn't tuned to
one voice: a dozen things to say to the demo, and six things it has no scene for, which must never be forced into one.
The thresholds were set on those (the tuning set); a fresh set, made after, says how it does on what it wasn't set on.
The page's own code does the hearing, in headless Chromium, on the CPU. Only the words and scenes are kept.

    uv run --with playwright python -m evals.say_it      # about 3 minutes; wav2vec 2.0 downloads once (95 MB)
"""
import functools
import http.server
import json
import statistics
import sys
import threading
import time
from pathlib import Path

import numpy as np

from evals.eyes_live import Quiet
from heyandy_meta.voice.local import LocalVoice

SCREEN = Path(__file__).resolve().parents[1] / "heyandy_meta" / "screen"
TUNING = ["Hey Andy, where are my keys?", "Help me reach it", "I'm ringing my phone", "Where's my passport?",
          "Is everything home?", "Show me the room", "What can you do?", "Where are my glasses?", "Let's play the cup game",
          "I'm going out", "What did you send to the cloud today?", "How did you do that?"]
NO_SCENE = ["Tell me a joke", "Turn on the lights", "I love you", "What's for dinner tonight?", "Call my daughter", "Play some music"]
FRESH = [("mms-eng", "Where is the remote?"), ("mms-eng", "Show me the weather radar"), ("eng", "This is my mug"),
         ("mms-eng", "Where did I put my keys?"), ("eng", "Are you okay?"), ("mms-eng", "What do you remember?"),
         ("mms-eng", "Good night"), ("eng", "Turn off the TV"), ("eng", "Where is my wallet?")]
FRESH_NO_SCENE = {"Good night", "Turn off the TV"}


def clips() -> list[dict]:
    out = []
    for voice in ("eng", "mms-eng"):
        mouth = LocalVoice(voice=voice, timeout=30)
        for text in TUNING:
            out.append({"set": "tuning", "voice": voice, "said": text, "audio": mouth.speak(text, rate=16000)})
        for text in NO_SCENE:
            out.append({"set": "tuning, no scene", "voice": voice, "said": text, "audio": mouth.speak(text, rate=16000)})
    for voice, text in FRESH:
        out.append({"set": "fresh, no scene" if text in FRESH_NO_SCENE else "fresh", "voice": voice, "said": text,
                    "audio": LocalVoice(voice=voice, timeout=30).speak(text, rate=16000)})
    return out


def main() -> None:
    from playwright.sync_api import sync_playwright

    made = clips()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(SCREEN)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/page.html")
        page.wait_for_function("typeof hearIt === 'function'")
        page.evaluate("() => earsReady()")
        for c in made:
            audio = np.asarray(c["audio"], dtype=np.float32).tolist()
            t = time.monotonic()
            r = page.evaluate("async (a) => { const h = await hearIt(Float32Array.from(a)); return [h.text, h.meant]; }", audio)
            took = time.monotonic() - t
            want = page.evaluate("(t) => route(t)", c["said"])
            got = page.evaluate("(t) => route(t)", r[1] or "")
            forced = page.evaluate("(m) => SAY.includes(m)", r[1] or "")
            row = {"set": c["set"], "voice": c["voice"], "said": c["said"], "heard": r[0], "taken as": r[1],
                   "scene wanted": want, "scene": got, "seconds": round(took, 2)}
            row["right"] = (not forced) if "no scene" in c["set"] else got == want
            rows.append(row)
            print(f"{'OK ' if row['right'] else 'XX '} {c['set']:17} {c['said']!r:42} heard {r[0]!r:36} -> {got}", flush=True)
        browser.close()
    server.shutdown()

    def part(name):
        rs = [r for r in rows if r["set"] == name]
        return f"{sum(r['right'] for r in rs)}/{len(rs)}"
    summary = {"tuning set, the right scene": part("tuning"), "tuning set, nothing forced (no scene)": part("tuning, no scene"),
               "fresh, the right scene": part("fresh"), "fresh, nothing forced (no scene)": part("fresh, no scene"),
               "seconds to hear, median": statistics.median(r["seconds"] for r in rows)}
    out = Path("evals/results") / f"say-it-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    sys.exit(main())
