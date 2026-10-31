"""Andy Finder: Reachy Mini looks around for a thing, finds it with SAM 3.1, turns to it and nods; and a phone that
rings, it turns to by ear, with nothing to set up.

A slim version of HeyAndy's search (github.com/AndyDM9/heyandy-meta): five views, middle first; SAM 3.1 on each frame;
the likeliest sighting becomes a head direction through the camera's published calibration; a confident sighting ends
the sweep early. The pictures go to SAM 3.1 on this computer when it's there, else to Meta's Model API (the page says
which). "Ring it" needs neither: the robot's own microphones say which side a ringing is on, and Reachy turns until it
hears it straight ahead (HeyAndy's companion/sound.py); with SAM 3.1 it then looks there. Nothing is saved.
"""
import base64
import io
import json
import math
import os
import threading
import time
import urllib.request

import numpy as np
from PIL import Image
from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose

VIEWS = ((0.0, 15.0), (28.0, 15.0), (-28.0, 15.0), (55.0, 15.0), (-55.0, 15.0))  # yaw (left +), pitch (down +)
SURE = 0.75  # a sighting this confident ends the sweep
HEAD_REACH = 30.0  # past this the base turns too
# At 1920x1080: Pollen publishes fx 1116 for the Lite; ours measured 1054 and 1049 (HeyAndy's evals/lens.py: the
# published value put things up to 4.7 degrees out near the edges of the view). The centre as published.
FX, CX, CY = 1054.0, 953.0, 542.0
LOCAL = "http://127.0.0.1:8090"
FOUND_SECONDS = 120  # the found shot stays on the page this long, in memory only

# Ring it (HeyAndy's companion/sound.py, measured on a Reachy Mini Lite): the array's angle follows a sound only 0.2 to
# 0.45 degrees for each degree the head turns, so a reading says which side, reliably, not how far. A ringing is chunks
# (0.1 s) four times louder than the room, most of them pure tone (spectral flatness at most 0.015; ringtones measured
# 0.000 to 0.008, a voice 0.03 to 0.06 at the median), with a side. Nothing is recorded: per chunk only those numbers.
TONAL, TONAL_SHARE, LOUDER, ENOUGH, QUIET_FLOOR = 0.015, 0.6, 4.0, 4, 0.004
WAIT_S, LISTEN_S, STEP_DEG, BRACKET, TURNS = 30.0, 1.6, 40.0, 30.0, 8
NEAR_RING_DEG = 35.0  # a thing SAM 3.1 sees further than this from where it rang isn't the one ringing


def flatness(x: np.ndarray, rate: int = 16000) -> float:
    """Spectral flatness over 300 Hz to 5 kHz: near 0 for a tone, near 1 for noise."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 64:
        return 1.0
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / rate)
    band = p[(f >= 300) & (f <= 5000)] + 1e-12
    return float(np.exp(np.mean(np.log(band))) / np.mean(band))


def reading(chunks: list, floor: float) -> float | None:
    """Which side of the head a ringing is on (positive left), or None: chunks are (when, loudness, flatness, side)."""
    loud = [c for c in chunks if c[1] >= LOUDER * max(floor, QUIET_FLOOR)]
    tones = [c for c in loud if c[2] <= TONAL]
    if not loud or len(tones) < TONAL_SHARE * len(loud):
        return None
    sides = [c[3] for c in tones if c[3] is not None]
    return float(np.median(sides)) if len(sides) >= ENOUGH else None


def turn_to(listen, turn, start: float, reach=(-150.0, 150.0), on_step=None) -> tuple[float | None, list]:
    """Turn the head towards a ringing, by the side heard only: the array's angle is too compressed to say how far,
    and within about 20 degrees of the sound it reads near zero either way (see above). So zeros say little; what
    places the sound is the nearest yaw it's clearly left of and the nearest it's clearly right of: the sound is
    between, in the middle. Turn STEP_DEG towards the side heard until there are both, then look between them where
    the gap is widest, until the two are BRACKET apart. listen() -> a reading at the head's yaw (None: no ringing);
    turn(yaw) moves the head (HeyAndy's companion/sound.py turn_to). Returns (the yaw facing it, or None if nothing was heard; the steps [(yaw, reading)])."""
    steps, yaw = [], start
    for _ in range(TURNS):
        turn(yaw)
        side = listen()
        if side is None:
            side = listen()  # a gap between rings: once more
            if side is None:
                break
        steps.append((yaw, side))
        if on_step:
            on_step(steps)
        left = [y for y, s in steps if s > 1.0]  # the sound is left of these yaws: it's at a larger one
        right = [y for y, s in steps if s < -1.0]
        lo, hi = (max(left) if left else None), (min(right) if right else None)
        zeros = [y for y, s in steps if abs(s) <= 1.0]
        if lo is not None and hi is not None:
            if hi - lo <= BRACKET or lo >= hi:  # placed (or the readings disagree: settle between them)
                return (lo + hi) / 2, steps
            inside = sorted({lo, hi, *(y for y, _ in steps if lo < y < hi)})
            a, b = max(zip(inside, inside[1:]), key=lambda g: g[1] - g[0])
            if b - a <= BRACKET / 2:
                return (lo + hi) / 2, steps
            nxt = (a + b) / 2
        elif lo is not None:  # left of everything clearly: further left (in smaller steps once near it)
            nxt = max(y for y, _ in steps) + (STEP_DEG if not zeros else STEP_DEG / 2)
        elif hi is not None:
            nxt = min(y for y, _ in steps) - (STEP_DEG if not zeros else STEP_DEG / 2)
        else:  # only near-zeros: it's near here; look a little either side
            nxt = start + (STEP_DEG / 2 if len(steps) % 2 else -STEP_DEG / 2)
        nxt = min(max(nxt, reach[0]), reach[1])
        if any(abs(nxt - y) < 1.0 for y, _ in steps):
            break
        yaw = nxt
    if not steps:
        return None, steps
    left = [y for y, s in steps if s > 1.0]
    right = [y for y, s in steps if s < -1.0]
    zeros = [y for y, s in steps if abs(s) <= 1.0]
    if left and right:
        return (max(left) + min(right)) / 2, steps
    if zeros:
        return sum(zeros) / len(zeros), steps
    return (max(left) + STEP_DEG / 2) if left else (min(right) - STEP_DEG / 2), steps
def where_to_look(x: float, y: float, w: int, h: int, yaw: float, pitch: float) -> tuple[float, float]:
    """The head direction (degrees) that puts pixel (x, y) of a view taken at (yaw, pitch) in the middle."""
    s = w / 1920
    return (yaw + math.degrees(math.atan2(CX * s - x, FX * s)),
            pitch + math.degrees(math.atan2(y - CY * (h / 1080), FX * s)))


def side(yaw: float) -> str:
    if abs(yaw) < 10:
        return "straight ahead"
    return ("a little " if abs(yaw) <= 35 else "") + "to my " + ("left" if yaw > 0 else "right")


class Local:
    """SAM 3.1 on this computer (HeyAndy's local/sam_server.py): pictures stay here."""

    where = "on this computer"

    def find(self, jpeg: bytes, thing: str) -> list[tuple[float, float, float, list]]:
        body = json.dumps({"image": base64.b64encode(jpeg).decode(), "query": thing, "min_score": 0.3}).encode()
        req = urllib.request.Request(LOCAL + "/segment", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return [(m["center"][0], m["center"][1], m["score"], m["box"]) for m in json.load(r)["masks"]]


class ModelApi:
    """SAM 3.1 through Meta's Model API: each look sends one picture to Meta."""

    where = "Meta's Model API (pictures go to Meta)"

    def __init__(self, key: str):
        from openai import OpenAI

        self.client = OpenAI(base_url="https://api.meta.ai/v1", api_key=key)

    def find(self, jpeg: bytes, thing: str) -> list[tuple[float, float, float, list]]:
        from meta_sam_parser import CompletedOutcome, SegmentationBoxRecord, image_segmentation_format

        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        out = self.client.responses.create(model="sam-3.1", metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
                                           input=[{"type": "message", "role": "user", "content": [
                                               {"type": "input_text", "text": thing},
                                               {"type": "input_image", "image_url": url}]}])
        parser = image_segmentation_format().create_parser()
        parser.push(out.output_text or "")
        found = []
        for r in parser.finish(CompletedOutcome()).result.records:
            if isinstance(r, SegmentationBoxRecord):
                b = r.bounds
                found.append(((b.left + b.right) / 2, (b.top + b.bottom) / 2, r.confidence or 0.5,
                              [b.left, b.top, b.right, b.bottom]))
        return found


def segmenter():
    try:
        with urllib.request.urlopen(LOCAL + "/health", timeout=2):
            return Local()
    except OSError:
        pass
    key = os.environ.get("MODEL_API_KEY")
    return ModelApi(key) if key else None


class AndyFinder(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        sam = segmenter()
        # What the page shows (static/): the search as it happens. Frames are held in memory only: the latest look while
        # searching, and the shot it was found in for FOUND_SECONDS; then dropped. Nothing is written anywhere.
        state = {"status": "What should I find?", "busy": False, "phase": "ready", "thing": "", "sound": None,
                 "where": sam.where if sam else "nowhere yet: start SAM 3.1 on this computer, or set MODEL_API_KEY",
                 "local": isinstance(sam, Local), "views": [], "look": None, "found": None, "history": [], "frame_v": 0}
        frame_now: dict = {"jpeg": None, "until": 0.0}
        asked: dict = {"thing": None, "ring": None}

        class Find(BaseModel):
            thing: str

        @self.settings_app.post("/ring")
        def ring_it(body: Find):
            thing = " ".join(body.thing.lower().split())[:40] or "phone"
            if state["busy"]:
                return state
            asked["ring"], state["busy"] = thing, True
            state.update(phase="listening", thing=thing, found=None, look=None, views=[],
                         sound={"steps": [], "facing": None, "waiting": WAIT_S}, status=f"Ring your {thing} now. I'm listening.")
            return state

        @self.settings_app.post("/find")
        def find(body: Find):
            thing = " ".join(body.thing.lower().split())[:40]
            if state["busy"] or not thing:
                return state
            asked["thing"], state["busy"], state["status"] = thing, True, f"Looking for your {thing}..."
            return state

        @self.settings_app.get("/status")
        def status():
            if frame_now["jpeg"] is not None and not state["busy"] and time.monotonic() > frame_now["until"]:
                frame_now["jpeg"], state["found"], state["look"] = None, None, None  # the picture goes
                state["frame_v"] += 1
            return state

        @self.settings_app.get("/frame.jpg")
        def frame_jpg():
            from fastapi import Response

            data = frame_now["jpeg"]
            if data is None:
                return Response(status_code=404)
            return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

        def show(jpeg: bytes | None, keep_s: float = 0.0) -> None:
            frame_now["jpeg"], frame_now["until"] = jpeg, time.monotonic() + keep_s
            state["frame_v"] += 1

        def look(yaw: float, pitch: float, duration: float = 0.8) -> None:
            # The daemon takes the head's direction in the room, the base's turn already in it: the head pose is the
            # whole yaw, and the base turns under it for what the head can't (HeyAndy found the base counted twice).
            head = max(-HEAD_REACH, min(HEAD_REACH, yaw))
            reachy_mini.goto_target(head=create_head_pose(yaw=yaw, pitch=pitch, degrees=True),
                                    body_yaw=math.radians(yaw - head), duration=duration)

        def frame() -> bytes | None:
            time.sleep(0.35)  # let the camera settle after the move
            for _ in range(20):
                data = reachy_mini.media.get_frame_jpeg()
                if data:
                    return data
                time.sleep(0.05)
            return None

        def wiggle(times: int = 3) -> None:
            for i in range(times * 2):
                a = math.radians(25 if i % 2 else -25)
                reachy_mini.goto_target(antennas=np.array([a, -a]), duration=0.15)
            reachy_mini.goto_target(antennas=np.array([0.0, 0.0]), duration=0.2)

        def search(thing: str, views=VIEWS, near: float | None = None) -> str:
            started, best = time.monotonic(), None  # (score, yaw, pitch, jpeg, box, w, h)
            state.update(phase="looking", thing=thing, found=None,
                         views=[{"yaw": y, "seen": 0, "best": 0.0, "done": False} for y, _ in views])
            for i, (yaw, pitch) in enumerate(views):
                if stop_event.is_set():
                    return "Stopped."
                state["look"] = {"view": i, "yaw": yaw, "side": side(yaw), "boxes": [], "w": 0, "h": 0}
                look(yaw, pitch)
                jpeg = frame()
                if jpeg is None:
                    continue
                w, h = Image.open(io.BytesIO(jpeg)).size
                seen = sam.find(jpeg, thing)
                show(jpeg)
                state["look"].update(w=w, h=h, boxes=[[round(v) for v in box] + [round(score, 2)] for _, _, score, box in seen])
                state["views"][i].update(seen=len(seen), best=round(max((sc for _, _, sc, _ in seen), default=0.0), 2), done=True)
                for x, y, score, box in seen:
                    at = where_to_look(x, y, w, h, yaw, pitch)
                    if near is not None and (abs(at[0] - near) > NEAR_RING_DEG or score < 0.5):
                        continue  # by its ring: one seen far from where it rang isn't the one ringing
                    # by its ring the nearest to where it rang (two monitors, the one by the speaker); else the surest
                    if best is None or (abs(at[0] - near) < abs(best[1] - near) if near is not None else score > best[0]):
                        best = (score, *at, jpeg, box, w, h)
                if best and best[0] >= SURE and (near is None or abs(best[1] - near) <= 12.0):
                    break
            if best is None:
                show(None)
                state.update(phase="missing", look=None)
                look(0.0, 10.0)
                for y in (-12.0, 12.0, -12.0, 0.0):  # a shake of the head
                    look(y, 10.0, 0.25)
                return f"I couldn't see your {thing}. Is it somewhere I can't look?"
            score, yaw, pitch, jpeg, box, w, h = best
            look(yaw, pitch)
            look(yaw, pitch + 8.0, 0.3)  # a nod towards it
            look(yaw, pitch, 0.3)
            seconds = round(time.monotonic() - started, 1)
            show(jpeg, FOUND_SECONDS)  # the shot it was found in, for the page's reveal; then it goes
            state.update(phase="found", look=None,
                         found={"thing": thing, "side": side(yaw), "yaw": round(yaw, 1), "score": round(score, 2),
                                "box": [round(v) for v in box], "w": w, "h": h, "seconds": seconds})
            state["history"] = ([{"thing": thing, "side": side(yaw), "at": time.time()}] + state["history"])[:6]
            wiggle()
            return f"There's your {thing}, {side(yaw)}."

        def ring(thing: str) -> str:
            """Ring it: listen while the person dials, turn to the ringing, then look there (with SAM 3.1) or point."""
            media, chunks, deaf = reachy_mini.media, [], threading.Event()

            def ear():  # numbers only, per tenth of a second: loudness, how pure a tone, which side
                while not deaf.is_set():
                    got = []
                    while len(got) < 10 and (c := media.get_audio_sample()) is not None:
                        got.append(c)
                    if not got:
                        time.sleep(0.02)
                        continue
                    a = np.concatenate(got)
                    mono = a.mean(axis=1) if a.ndim == 2 else a
                    d = media.get_DoA()
                    side_ = 90.0 - math.degrees(d[0]) if d and d[1] else None
                    chunks.append((time.monotonic(), float(np.sqrt(np.mean(mono ** 2))), flatness(mono), side_))
                    del chunks[:-400]

            def floor() -> float:
                levels = sorted(c[1] for c in chunks)
                return max(levels[len(levels) // 5] if levels else 0.0, QUIET_FLOOR)

            def listen() -> float | None:
                t = time.monotonic()
                time.sleep(LISTEN_S)
                return reading([c for c in chunks if c[0] >= t], floor())

            def turn(yaw: float) -> None:
                look(yaw, 0.0)
                time.sleep(0.5)  # still: the motors mustn't be what it hears

            media.start_recording()
            hearing = threading.Thread(target=ear, daemon=True)
            hearing.start()
            try:
                turn(0.0)
                rang = False
                for left in range(int(WAIT_S / LISTEN_S), 0, -1):  # the person dials meanwhile
                    state["sound"]["waiting"] = round(left * LISTEN_S)
                    if stop_event.is_set():
                        return "Stopped."
                    if listen() is not None:
                        rang = True
                        break
                state["sound"]["waiting"] = None
                if not rang:
                    state.update(phase="unheard")
                    look(0.0, 10.0)
                    return f"I didn't hear it ring. Is the ringer on? Tap Ring it, and call your {thing} again."
                state["status"] = "I hear it. Turning to the sound..."
                facing, steps = turn_to(listen, turn, 0.0,
                                        on_step=lambda st: state["sound"].update(steps=[[round(y, 1), round(v, 1)] for y, v in st]))
            finally:
                deaf.set()
                hearing.join(1.0)
                media.stop_recording()
            if facing is None:
                state.update(phase="unheard")
                return "The ringing stopped before I could turn to it. Call it again, and tap Ring it."
            state["sound"]["facing"] = round(facing, 1)
            if sam:  # look where it rang, and only there
                said = search(thing, views=((facing, 15.0), (facing + 22.0, 20.0), (facing - 22.0, 20.0), (facing, 32.0)), near=facing)
                if state["phase"] == "found":
                    return "I followed the ringing. " + said
            state.update(phase="heard", look=None, found=None)
            look(facing, 15.0)
            look(facing, 23.0, 0.3)  # a nod towards it
            look(facing, 15.0, 0.3)
            return (f"I can hear it, but I can't see it: it's ringing {side(facing)}, where I'm looking. It may be under something."
                    if sam else f"It's ringing {side(facing)}, where I'm looking.")

        while not stop_event.is_set():
            thing, ringing = asked["thing"], asked["ring"]
            if thing is None and ringing is None:
                time.sleep(0.05)
                continue
            asked["thing"] = asked["ring"] = None
            try:
                if ringing is not None:
                    state["status"] = ring(ringing)
                else:
                    state["status"] = search(thing) if sam else "I can't see yet: " + state["where"]
            except Exception as e:  # noqa: BLE001 - say what went wrong on the page, and keep going
                state.update(status=f"Something went wrong: {type(e).__name__}", phase="ready", look=None)
            finally:
                state["busy"] = False


if __name__ == "__main__":
    app = AndyFinder()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
