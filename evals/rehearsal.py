"""The dress rehearsal: each line of the video's storyboard (docs/demo-script.md) as a whole turn on the robot, before
the cameras roll.

Each line is spoken in Andy's own voice and heard by its own ears, through the voice loop (the second listening for
another language too), and Andy takes the turn on the robot as it will on camera: it looks, points, speaks, and the TV
shows it (http://127.0.0.1:8765, while Andy's own service is stopped). For each shot: what Andy heard and said, how
long it took, whether it pointed, and, if the shot needs something it didn't do, what to fix before filming ("put the
glasses where the robot can see them, away from screens"). Two shots need a person or a wait and aren't rehearsed
here: "what am I holding?" and the reminder two minutes later. The offline shot is played offline (as if the cable
were out). Only words and numbers are kept, never a picture or a sound.

    systemctl --user stop heyandy-app
    set -a; . ~/.config/heyandy-meta/env; set +a          # the cloud shots: Muse Image and Muse Spark
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 uv run python -m evals.rehearsal
    systemctl --user start heyandy-app
"""
import argparse
import json
import os
import tempfile
import threading
import time
from pathlib import Path

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.language import LANGUAGES
from heyandy_meta.voice.local import LocalVoice
from heyandy_meta.voice.loop import VoiceLoop

# (shot, language, what's said, what the shot needs): point / follow / cloud / zh
SHOTS = [
    ("the uncut find", "en", "Hey Andy, where are my glasses?", "point"),
    ("follow the mug", "en", "Hey Andy, follow the mug.", "follow"),
    ("several things at once", "en", "Hey Andy, find the cup and remind me in two minutes to call Sam.", "point"),
    ("the network unplugged", "en", "Hey Andy, where's the remote?", "point offline"),
    ("the room in 3D", "en", "Hey Andy, show me the room.", ""),
    ("a picture", "en", "Hey Andy, draw me a lighthouse at dawn.", "cloud"),
    ("the weather radar on the TV", "en", "Hey Andy, show me the weather radar on the TV.", "cloud"),
    ("in Mandarin, nothing said in English first", "zh", "安迪，我的眼镜在哪里？", "point zh"),
    ("back to English", "en", "Andy, speak English.", "en"),
    ("an emergency said (if it's in the video)", "en", "Hey Andy, I fell and I can't get up.", "point"),
]
NOT_HERE = ["\"What am I holding?\": needs someone holding something up to the robot.",
            "The reminder two minutes later: needs the wait, and a person for Andy to turn to."]
# what each shot looks for, where the rules can't read it from the line: the Mandarin line asks for the glasses, and
# the emergency is answered with 911 and the phone found
THING = {"in Mandarin, nothing said in English first": "glasses", "an emergency said (if it's in the video)": "phone"}
FIX = {
    "point": "Andy didn't point: put {thing} where the robot can see it, on the table in front, away from screens "
             "(it skips pictures on a TV, and its own TV may be showing the last thing it found).",
    "follow": "The follow didn't start: is a mug in view?",
    "cloud": "The cloud shot didn't work: is MODEL_API_KEY set (~/.config/heyandy-meta/env) and the network up?",
    "zh": "Andy didn't switch to Mandarin: say it closer to the robot, or start with \"Andy, speak Mandarin\".",
    "en": "Andy didn't come back to English: say \"Andy, speak English\" again.",
}


def build():
    from heyandy_meta.__main__ import build as make

    return make(argparse.Namespace(
        data=tempfile.mkdtemp(prefix="andy-rehearsal-"), robot=True, voice=True,
        no_cloud=not os.environ.get("MODEL_API_KEY"), offline=False, no_local_agent=False,
        glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094", sam="http://127.0.0.1:8090",
        voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096", voice_name="eng", home="", staged_scene=False))


def shot(andy, loop, name: str, code: str, line: str, needs: str) -> dict:
    said: list[str] = []
    say = andy.body.say
    andy.body.say = lambda text, *a, **k: (said.append(text), say(text, *a, **k))[1]
    if "offline" in needs:
        andy.set_online(False)
    stopper = None
    if "follow" in needs:  # stop the follow after a few seconds, as "Stop." will on camera
        stopper = threading.Timer(8.0, andy.stop_following)
        stopper.start()
    try:
        audio = LocalVoice(voice=LANGUAGES[code].voice, timeout=30).speak(line)
        start = time.monotonic()
        andy.voice.language = andy.asr_language
        heard = andy.voice.transcribe(audio)
        text = loop._which_language(heard, audio, andy.voice)
        reply = loop.heard(text) or ""
        took = time.monotonic() - start
    finally:
        andy.body.say = say
        if "offline" in needs:
            andy.set_online(True)
        if stopper:
            stopper.cancel()
    pointed = bool(getattr(andy, "_pointed", False))
    problems = []
    if "point" in needs and not pointed:
        thing = THING.get(name) or parse(line.split(",", 1)[-1]).thing
        problems.append(FIX["point"].format(thing=f"the {thing}" if thing else "it"))
    if "follow" in needs and not any("follow" in s_.lower() or "watching" in s_.lower() for s_ in said + [reply]):
        problems.append(FIX["follow"])
    if "cloud" in needs and any(w in reply.lower() for w in ("not connected", "can't look", "can't draw", "can't show", "offline")):
        problems.append(FIX["cloud"])
    if "zh" in needs and andy.language != "zh":
        problems.append(FIX["zh"])
    if needs == "en" and andy.language != "en":
        problems.append(FIX["en"])
    return {"shot": name, "said": line, "heard": heard, "andy said": said, "seconds": round(took, 1), "pointed": pointed,
            "language after": andy.language, "ok": not problems, "fix": problems}


def main() -> None:
    andy = build()
    loop = VoiceLoop(andy)
    rows = []
    for name, code, line, needs in SHOTS:
        r = shot(andy, loop, name, code, line, needs)
        rows.append(r)
        print(f"{'OK  ' if r['ok'] else 'FIX '} {name}: {r['seconds']} s{', pointed' if r['pointed'] else ''}"
              f" | {' / '.join(s_[:70] for s_ in r['andy said'][:2])}", flush=True)
        for f in r["fix"]:
            print(f"      -> {f}", flush=True)
        time.sleep(2.0)
    andy.body.look(0, 0)
    for n in NOT_HERE:
        print(f"NOT REHEARSED: {n}")
    out = Path("evals/results") / f"rehearsal-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "shots": rows, "not rehearsed": NOT_HERE,
                               "ready": all(r["ok"] for r in rows)}, indent=1, ensure_ascii=False))
    print(f"\n{'READY TO FILM' if all(r['ok'] for r in rows) else 'FIX THE SHOTS ABOVE, THEN RUN THIS AGAIN'} ({out})")


if __name__ == "__main__":
    main()
