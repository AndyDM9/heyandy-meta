"""Andy Finder: Reachy Mini looks around for a thing, finds it with SAM 3.1, turns to it and nods; and a phone that
rings, it turns to by ear, with nothing to set up.

A slim version of HeyAndy's search (github.com/AndyDM9/heyandy-meta): five views, middle first; SAM 3.1 on each frame;
the likeliest sighting becomes a head direction through each pixel's true ray, with the lens HeyAndy measured; a
confident sighting ends the sweep early. Then Reachy turns to it, nods, and its own camera checks the point: how many
degrees off the thing is, corrected once if it's more than 3. Three things HeyAndy measured on a Lite (November 1) are
built in: the camera's focus is held on the table (its continuous autofocus hunts after every turn of the head, and
small things like keys went unseen), a frame is taken only once the picture has caught up with the head (half a
second), and after the nod the head is read back and lifted (it sags about 4 degrees, and where it stops varies). The
pictures go to SAM 3.1 on this computer when it's there, else to Meta's Model API (the page says which). "Ring it" needs neither: the robot's own microphones say which side a ringing is on, and Reachy turns until it
hears it straight ahead (HeyAndy's companion/sound.py); with SAM 3.1 it then looks there. Nothing is saved.
"""
import base64
import io
import json
import math
import os
import subprocess
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
FRESH_S = 0.5  # the picture runs behind the head: frames are sharp 0.34 to 0.45 s after a move ends (measured)
AIM_OK, AIM_NEAR = 3.0, 8.0  # a point this far off is corrected once; a thing further than this isn't the one pointed at
FOCUS_STEPS = (350, 425, 500, 575, 650, 750)  # the Lite's lens on a desk: sharp only near 500 (of 0 to 1023)
# SAM 3.1 asked for "keys" outlines each key of a keyboard too (28 of 28 masks on one, HeyAndy measured on the Lite);
# "bunch of keys" finds only the keys (HeyAndy's models/common.py)
ASK = {"keys": "bunch of keys", "key": "set of keys", "car keys": "bunch of keys", "house keys": "bunch of keys"}
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
    """The head direction (degrees, yaw left +, pitch down +) that puts pixel (x, y) of a view taken at (yaw, pitch) in
    the middle: the pixel's ray in the room (HeyAndy's finder/geometry.py). Adding the pixel's two angles to the view's,
    as this did before, is right only on the frame's middle row and column: with the head tilted down, a thing at the
    side of the frame sits higher than that says (HeyAndy measured sightings of one thing disagreeing by a median 1.7
    degrees that way, 1.0 with the true ray)."""
    s = w / 1920
    a, b = (x - CX * s) / (FX * s), (y - CY * (h / 1080)) / (FX * s)
    ps, th = math.radians(yaw), math.radians(pitch)
    forward = (math.cos(th) * math.cos(ps), math.cos(th) * math.sin(ps), -math.sin(th))  # x ahead, y left, z up
    right = (math.sin(ps), -math.cos(ps), 0.0)
    down = (-math.sin(th) * math.cos(ps), -math.sin(th) * math.sin(ps), -math.cos(th))
    v = [forward[i] + a * right[i] + b * down[i] for i in range(3)]
    return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.atan2(-v[2], math.hypot(v[0], v[1])))


def off_middle(x: float, y: float, w: int, h: int) -> float:
    """How many degrees pixel (x, y) is from the middle of the view: how far off a point is."""
    s = w / 1920
    return math.degrees(math.atan(math.hypot(x - CX * s, y - CY * (h / 1080)) / (FX * s)))


def head_angles(pose) -> tuple[float, float]:
    """Yaw (left +) and pitch (down +) in degrees from the daemon's 4x4 head pose (in the room, the base's turn in it)."""
    return math.degrees(math.atan2(pose[1][0], pose[0][0])), math.degrees(math.asin(-max(-1.0, min(1.0, pose[2][0]))))


def camera_device(run=subprocess.run) -> str | None:
    """The robot camera's video device, from v4l2-ctl's list; None without v4l2-ctl or a "Reachy Mini Camera" (a
    wireless Reachy's camera isn't one: its focus is left alone)."""
    try:
        lines = run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=5).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return None
    for i, line in enumerate(lines):
        if "Reachy Mini Camera" in line:
            for dev in lines[i + 1:]:
                if dev.strip().startswith("/dev/video"):
                    return dev.strip()
                if not dev.strip():
                    break
    return None


def sharpness(jpeg: bytes) -> float:
    """How sharp a frame is: the variance of its edges (a Laplacian) on a half-size grey copy. A number, no picture kept."""
    g = Image.open(io.BytesIO(jpeg)).convert("L")
    g = np.asarray(g.resize((max(1, g.width // 2), max(1, g.height // 2))), dtype=np.float32)
    return float((4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]).var())


class Focus:
    """The camera's focus, held on the table while the app runs, and given back as it was when it stops. HeyAndy found
    (November 1) that the Lite's continuous autofocus hunts for seconds after every turn of the head: a cup is found
    out of focus, a bunch of keys isn't (7 of 16 frames facing them with autofocus, 13 of 16 with focus held). Each step
    is tried (the lower of two fresh frames' sharpness), then half a step either side of the sharpest; if nothing stands
    out (a blank wall in view), autofocus is left on. Without v4l2-ctl or the camera, nothing changes."""

    def __init__(self, run=subprocess.run):
        self.run, self.dev, self.was, self.held = run, camera_device(run), None, None

    def _ctl(self, **kw) -> None:
        self.run(["v4l2-ctl", "-d", self.dev] + [a for k, v in kw.items() for a in ("-c", f"{k}={v}")],
                 check=True, capture_output=True, timeout=5)

    def hold(self, look, fresh, steps=FOCUS_STEPS, settle_s: float = 0.6) -> int | None:
        """look(yaw, pitch) turns the head, fresh() returns a JPEG taken after it; the focus held, or None."""
        if not self.dev:
            return None
        try:
            out = self.run(["v4l2-ctl", "-d", self.dev, "--get-ctrl", "focus_automatic_continuous"],
                           capture_output=True, text=True, timeout=5).stdout
            self.was = int(out.rsplit(":", 1)[1]) if ":" in out else 1
            self._ctl(focus_automatic_continuous=0)
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
        tried: dict[int, float] = {}

        def measure(focus: int) -> float:
            if focus not in tried:
                self._ctl(focus_absolute=focus)
                time.sleep(settle_s)  # the lens moving, and the picture's delay behind it
                fresh()  # may be from before the lens moved
                tried[focus] = min(sharpness(fresh() or b"") for _ in range(2))
            return tried[focus]

        try:
            look(0.0, 15.0)  # the table in front
            best = max(steps, key=measure)
            half = max(1, min(abs(a - b) for a, b in zip(steps, steps[1:])) // 2)
            best = max((best - half, best, best + half), key=measure)
            if tried[best] < 2.0 * min(tried.values()):  # nothing stood out: leave focusing to the camera
                self._ctl(focus_automatic_continuous=1)
                return None
            self._ctl(focus_absolute=best)
            self.held = best
            return best
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError):  # a frame that won't open: as it was
            self.release()
            return None

    def release(self) -> None:
        """Autofocus as it was before the app (on, unless something else had turned it off)."""
        if self.dev and self.was is not None:
            try:
                self._ctl(focus_automatic_continuous=self.was)
            except (OSError, subprocess.SubprocessError):
                pass
            self.held = None


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

        moved = {"at": -math.inf}

        def look(yaw: float, pitch: float, duration: float = 0.8) -> None:
            # The daemon takes the head's direction in the room, the base's turn already in it: the head pose is the
            # whole yaw, and the base turns under it for what the head can't (HeyAndy found the base counted twice).
            head = max(-HEAD_REACH, min(HEAD_REACH, yaw))
            reachy_mini.goto_target(head=create_head_pose(yaw=yaw, pitch=pitch, degrees=True),
                                    body_yaw=math.radians(yaw - head), duration=duration)  # returns when it's there
            moved["at"] = time.monotonic()

        def next_frame(wait_s: float = 1.0) -> bytes | None:
            for _ in range(max(1, int(wait_s / 0.05))):
                data = reachy_mini.media.get_frame_jpeg()
                if data:
                    return data
                time.sleep(0.05)
            return None

        def fresh() -> bytes | None:
            """A frame from after the last move: the picture runs behind the head (sharp 0.34 to 0.45 s after)."""
            left = FRESH_S - (time.monotonic() - moved["at"])
            if left > 0:
                time.sleep(left)
            stale = next_frame()  # the camera hands each frame over once: this one may be from mid-move
            return next_frame(0.5) or stale

        def measured() -> tuple[float, float] | None:
            """Where the head really looks: it stops a few degrees from where it's sent, differently each time."""
            try:
                return head_angles(reachy_mini.get_current_head_pose())
            except Exception:  # noqa: BLE001 - an older daemon: the direction it was sent is all there is
                return None

        def frame(yaw: float, pitch: float) -> tuple[bytes | None, float, float]:
            """A fresh frame, and where the head really was for it."""
            data = fresh()
            now = measured()
            return (data, *now) if now else (data, yaw, pitch)

        def point(yaw: float, pitch: float, nod: bool = True) -> None:
            """Turn to it and nod; then read the head back and correct it, up to twice: after the nod it sags (a median
            3.9 degrees on HeyAndy's Lite), and where it stops varies by up to 8. Steady 0.3 s after each move."""
            look(yaw, pitch, 0.8 if nod else 0.4)
            if nod:
                look(yaw, pitch + 8.0, 0.3)  # a nod towards it
                look(yaw, pitch, 0.3)
            sent = [yaw, pitch]
            for _ in range(2):
                time.sleep(0.3)
                now = measured()
                if not now or max(abs(yaw - now[0]), abs(pitch - now[1])) <= 1.5:
                    return
                sent = [sent[0] + max(-10.0, min(10.0, yaw - now[0])), sent[1] + max(-10.0, min(10.0, pitch - now[1]))]
                look(*sent, 0.3)

        def check_aim(thing: str, yaw: float, pitch: float) -> tuple[float | None, float, float]:
            """Its own camera checks the point: one fresh frame from where the head now faces, SAM 3.1 on it, the
            outline nearest the middle; how many degrees off the middle it is, and where it really is. (None, yaw,
            pitch) if it can't tell: nothing near the middle, or no frame."""
            jpeg, fy, fp = frame(yaw, pitch)
            if jpeg is None:
                return None, yaw, pitch
            w, h = Image.open(io.BytesIO(jpeg)).size
            seen = [m for m in sam.find(jpeg, ASK.get(thing, thing)) if m[2] >= 0.3]
            near = min(seen, key=lambda m: off_middle(m[0], m[1], w, h), default=None)
            if near is None or off_middle(near[0], near[1], w, h) > AIM_NEAR:
                return None, yaw, pitch
            return round(off_middle(near[0], near[1], w, h), 1), *where_to_look(near[0], near[1], w, h, fy, fp)

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
                jpeg, fy, fp = frame(yaw, pitch)
                if jpeg is None:
                    continue
                w, h = Image.open(io.BytesIO(jpeg)).size
                seen = sam.find(jpeg, ASK.get(thing, thing))
                show(jpeg)
                state["look"].update(w=w, h=h, boxes=[[round(v) for v in box] + [round(score, 2)] for _, _, score, box in seen])
                state["views"][i].update(seen=len(seen), best=round(max((sc for _, _, sc, _ in seen), default=0.0), 2), done=True)
                for x, y, score, box in seen:
                    at = where_to_look(x, y, w, h, fy, fp)  # from where the head really was
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
            state["look"] = {"view": -1, "yaw": yaw, "side": side(yaw), "boxes": [[round(v) for v in box] + [round(score, 2)]],
                             "w": w, "h": h, "pointing": True}  # the page: found, turning to it, then checking the point
            point(yaw, pitch)
            aim, yaw, pitch = check_aim(thing, yaw, pitch)
            if aim is not None and aim > AIM_OK:  # off: once more, by what the camera showed, without another nod
                point(yaw, pitch, nod=False)
                aim, yaw, pitch = check_aim(thing, yaw, pitch)
            seconds = round(time.monotonic() - started, 1)
            show(jpeg, FOUND_SECONDS)  # the shot it was found in, for the page's reveal; then it goes
            state.update(phase="found", look=None,
                         found={"thing": thing, "side": side(yaw), "yaw": round(yaw, 1), "score": round(score, 2),
                                "box": [round(v) for v in box], "w": w, "h": h, "seconds": seconds, "aim": aim})
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

        focus = Focus()
        if sam and focus.dev:  # finding needs the camera sharp on the table; "Ring it" doesn't use it
            state.update(busy=True, status="Getting my eyes ready: focusing on the table...")
            try:
                focus.hold(look, fresh)
            finally:
                state.update(busy=False, status="What should I find?")
        try:
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
        finally:
            focus.release()  # the camera's autofocus as it was before the app


if __name__ == "__main__":
    app = AndyFinder()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
