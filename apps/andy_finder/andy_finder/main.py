"""Andy Finder: Reachy Mini looks around for a thing, finds it with SAM 3.1, turns to it and nods.

A slim version of HeyAndy's search (github.com/AndyDM9/heyandy-meta): five views, middle first; SAM 3.1 on each frame;
the likeliest sighting becomes a head direction through the camera's published calibration; a confident sighting ends
the sweep early. The pictures go to SAM 3.1 on this computer when it's there, else to Meta's Model API (the page says
which). Nothing is saved.
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

    def find(self, jpeg: bytes, thing: str) -> list[tuple[float, float, float]]:
        body = json.dumps({"image": base64.b64encode(jpeg).decode(), "query": thing, "min_score": 0.3}).encode()
        req = urllib.request.Request(LOCAL + "/segment", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return [(m["center"][0], m["center"][1], m["score"]) for m in json.load(r)["masks"]]


class ModelApi:
    """SAM 3.1 through Meta's Model API: each look sends one picture to Meta."""

    where = "Meta's Model API (pictures go to Meta)"

    def __init__(self, key: str):
        from openai import OpenAI

        self.client = OpenAI(base_url="https://api.meta.ai/v1", api_key=key)

    def find(self, jpeg: bytes, thing: str) -> list[tuple[float, float, float]]:
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
                found.append(((b.left + b.right) / 2, (b.top + b.bottom) / 2, r.confidence or 0.5))
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
        state = {"status": "What should I find?", "busy": False,
                 "where": sam.where if sam else "nowhere yet: start SAM 3.1 on this computer, or set MODEL_API_KEY"}
        asked: dict = {"thing": None}

        class Find(BaseModel):
            thing: str

        @self.settings_app.post("/find")
        def find(body: Find):
            thing = " ".join(body.thing.lower().split())[:40]
            if state["busy"] or not thing:
                return state
            asked["thing"], state["busy"], state["status"] = thing, True, f"Looking for your {thing}..."
            return state

        @self.settings_app.get("/status")
        def status():
            return state

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

        def search(thing: str) -> str:
            best = None  # (score, yaw, pitch)
            for yaw, pitch in VIEWS:
                if stop_event.is_set():
                    return "Stopped."
                look(yaw, pitch)
                jpeg = frame()
                if jpeg is None:
                    continue
                w, h = Image.open(io.BytesIO(jpeg)).size
                for x, y, score in sam.find(jpeg, thing):
                    if best is None or score > best[0]:
                        best = (score, *where_to_look(x, y, w, h, yaw, pitch))
                if best and best[0] >= SURE:
                    break
            if best is None:
                look(0.0, 10.0)
                for y in (-12.0, 12.0, -12.0, 0.0):  # a shake of the head
                    look(y, 10.0, 0.25)
                return f"I couldn't see your {thing}. Is it somewhere I can't look?"
            _, yaw, pitch = best
            look(yaw, pitch)
            look(yaw, pitch + 8.0, 0.3)  # a nod towards it
            look(yaw, pitch, 0.3)
            wiggle()
            return f"There's your {thing}, {side(yaw)}."

        while not stop_event.is_set():
            thing = asked["thing"]
            if thing is None:
                time.sleep(0.05)
                continue
            asked["thing"] = None
            try:
                state["status"] = search(thing) if sam else "I can't see yet: " + state["where"]
            except Exception as e:  # noqa: BLE001 - say what went wrong on the page, and keep going
                state["status"] = f"Something went wrong: {type(e).__name__}"
            finally:
                state["busy"] = False


if __name__ == "__main__":
    app = AndyFinder()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
