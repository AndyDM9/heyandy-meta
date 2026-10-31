"""Find it by sound, on the robot: does Andy turn to a ringing, and to the same place from wherever it starts?

A ringtone (two tones, as phones ring; and a struck-bar tune, as phones ship them) plays through this computer's
monitor speakers while Andy turns towards it (companion/sound.py turn_to), starting with the head well to one side,
straight ahead, and well to the other. The same sound must end at the same yaw from every start. A spoken sentence
(Andy's own voice, SeamlessM4T v2) is played the same way: a voice must not be taken for a ringing. Only numbers are
kept. Where the speakers really are isn't known here (two monitors carry the sound), so the founder's test with a
phone at a known place is what measures the aim.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 \\
        uv run python -m evals.sound
    systemctl --user start heyandy-app

With --app "phone,computer monitor" it runs the whole turn through the app instead (see through_the_app).
"""
import argparse
import json
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

from heyandy_meta.companion.sound import Ear, reading, turn_to

SINK = "alsa_output.pci-0000_01_00.1.hdmi-stereo"  # the monitors' speakers (DisplayPort audio)


def ringtone(rate: int = 48000, seconds: float = 16.0) -> np.ndarray:
    t = np.arange(int(rate * 0.4)) / rate
    burst = (0.5 * np.sin(2 * np.pi * 1400 * t) + 0.5 * np.sin(2 * np.pi * 1750 * t)) * np.minimum(1, (0.4 - t) / 0.02)
    ring = np.concatenate([burst, np.zeros(int(rate * 0.2)), burst, np.zeros(int(rate * 1.0))])
    return np.tile(ring, int(seconds / 2.0)) * 0.6


def marimba(rate: int = 48000, seconds: float = 16.0) -> np.ndarray:
    """A ringtone as phones ship them: a struck-bar tune (harmonics that fade), repeated."""
    from heyandy_meta.voice.earcons import NOTE

    out = []
    for n in ["E5", "G5", "C6", "G5", "E6", "C6", "G5", "E5"]:
        t = np.arange(int(rate * 0.18)) / rate
        f = NOTE[n]
        tone = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d) for k, a, d in ((1, 1.0, 9), (3.9, 0.3, 25), (9.2, 0.1, 40)))
        out.append(tone * np.minimum(1, (0.18 - t) / 0.01))
    out.append(np.zeros(int(rate * 0.4)))
    x = np.tile(np.concatenate(out), int(seconds / 1.84) + 1)
    return x * (0.6 / np.max(np.abs(x)))


def write(path: str, x: np.ndarray, rate: int) -> str:
    with wave.open(path, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def through_the_app(things: list[str], out: str) -> None:
    """The whole turn, as the service runs it (the voice too, a scratch memory): "Ring it now", the turns, the look
    with SAM 3.1 around the way it heard, and the point. The microphones feed the app's ear as the voice loop does."""
    import argparse as _a

    from heyandy_meta.__main__ import build

    andy = build(_a.Namespace(
        data=tempfile.mkdtemp(prefix="andy-sound-app-"), robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    andy.wait = time.sleep
    stop = threading.Event()

    def hearing():
        for samples, flag, yaw in andy.body.listen(stop):
            andy.ear(samples, flag, yaw)

    threading.Thread(target=hearing, daemon=True).start()
    andy.body.look(0, 0)
    time.sleep(3.0)  # the room's own noise
    folder = tempfile.mkdtemp(prefix="andy-sound-")
    ring = write(f"{folder}/ring.wav", ringtone(seconds=40.0), 48000)
    runs = []
    for thing in things:
        andy.body.look(50.0, 0.0)  # start facing well away from the sound
        time.sleep(1.0)
        player = subprocess.Popen(["paplay", f"--device={SINK}", ring])
        time.sleep(1.0)
        began = time.monotonic()
        with andy.lock:
            words = andy.find_by_sound(thing)
        player.terminate()
        found = andy.finder.last_found
        runs.append({"thing": thing, "said": words, "seconds": round(time.monotonic() - began, 1),
                     "why": andy._reason,
                     "found": None if found is None else {"label": found.label, "yaw": round(found.yaw, 1), "aim_deg": found.aim_deg}})
        print(runs[-1])
        andy.say(words)
        time.sleep(2.0)
    stop.set()
    andy.body.look(0, 0)
    path = Path(out) / f"sound-app-{time.strftime('%Y%m%d-%H%M')}.json"
    path.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "runs": runs}, indent=1))
    print(f"saved {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--starts", default="-50,0,50")
    ap.add_argument("--app", default="", help="through the whole app instead, for these things (e.g. phone,computer monitor)")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    if args.app:
        return through_the_app(args.app.split(","), args.out)
    from heyandy_meta.robot.reachy_mini import ReachyBody
    from heyandy_meta.voice.local import LocalVoice

    body = ReachyBody()
    ear, stop = Ear(head=lambda: body.yaw), threading.Event()

    def hearing():
        for samples, flag, yaw in body.listen(stop):
            ear(samples, flag, yaw)

    threading.Thread(target=hearing, daemon=True).start()
    body.look(0, 0)
    time.sleep(2.0)  # the room's own noise, before anything plays
    floor = ear.floor()

    def turn(yaw):
        body.look(yaw, 0.0)
        time.sleep(0.5)  # still, so the motors aren't what's heard

    heard = []

    def listen():
        t = time.monotonic()
        time.sleep(1.6)
        chunks = ear.since(t)
        loud = [c for c in chunks if c[1] >= 4 * floor]
        heard.append({"chunks": len(chunks), "loud": len(loud), "tonal": sum(c[2] <= 0.015 for c in loud),
                      "with_side": sum(c[2] <= 0.015 and c[3] is not None for c in loud)})
        return reading(chunks, floor)

    folder = tempfile.mkdtemp(prefix="andy-sound-")
    sounds = {"ringtone": write(f"{folder}/ring.wav", ringtone(), 48000),
              "marimba": write(f"{folder}/marimba.wav", marimba(), 48000)}
    speech = LocalVoice().speak("Where did I put my phone? I had it a minute ago, in the kitchen, I think. "
                                "Could you have a look for it on the table, please?", rate=16000)
    sounds["voice"] = write(f"{folder}/talk.wav", speech * (0.6 / max(1e-6, float(np.max(np.abs(speech))))), 16000)
    runs = []
    for kind, f in sounds.items():
        for start in (float(s) for s in args.starts.split(",")):
            if kind == "voice" and start != 0.0:
                continue
            body.look(start, 0.0)
            time.sleep(0.8)
            player = subprocess.Popen(["paplay", f"--device={SINK}", f])
            began = time.monotonic()
            heard.clear()
            yaw, steps = turn_to(listen, turn, start)
            player.terminate()
            runs.append({"sound": kind, "start": start, "facing": None if yaw is None else round(yaw, 1), "heard": list(heard),
                         "steps": [[round(y, 1), round(s, 1)] for y, s in steps], "seconds": round(time.monotonic() - began, 1)})
            print(runs[-1])
            time.sleep(1.0)
    stop.set()
    body.look(0, 0)
    ends = {k: [r["facing"] for r in runs if r["sound"] == k and r["facing"] is not None] for k in ("ringtone", "marimba")}
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "room_floor": round(floor, 4),
              "ringings_faced": sum(len(v) for v in ends.values()), "of": sum(1 for r in runs if r["sound"] != "voice"),
              "spread_deg": {k: round(max(v) - min(v), 1) for k, v in ends.items() if v},
              "voice_taken_for_a_ringing": any(r["facing"] is not None for r in runs if r["sound"] == "voice"), "runs": runs}
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=1))
    out = Path(args.out) / f"sound-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
