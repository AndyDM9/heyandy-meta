"""Andy's TV page on sample data: no robot, no camera, no models. The picture is drawn here, not taken in a home.

    uv run python scripts/demo_screen.py found        # then open http://127.0.0.1:8765
    uv run python scripts/demo_screen.py --cycle      # every scene in turn, 8 s each
    python scripts/demo_screen.py --public --host 0.0.0.0 --port 7860   # the Hugging Face Space: each visitor picks
                                                                         # a scene; nothing they do reaches anyone else

Scenes: idle, finding, found, answer, drawing, memory, help.
"""
import argparse
import functools
import io
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heyandy_meta.finder.search import Found  # noqa: E402
from heyandy_meta.models.common import Mask  # noqa: E402
from heyandy_meta.robot.body import Frame  # noqa: E402
from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

SCENES = ("idle", "finding", "found", "answer", "drawing", "memory", "help")
SAMPLE_DRAWING = Path(__file__).resolve().parents[1] / "docs" / "images" / "sample-drawing.webp"  # made by Muse Image


@functools.lru_cache(maxsize=1)
def sample_frame() -> tuple[bytes, Mask]:
    """A drawn table with a blue mug on it, at the camera's 1920x1080, and the mug's outline."""
    img = Image.new("RGB", (1920, 1080), (196, 184, 168))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 640, 1920, 1080), fill=(139, 104, 74))  # the table top
    d.rectangle((300, 330, 760, 640), fill=(60, 64, 72))  # a laptop
    d.rectangle((320, 350, 740, 600), fill=(120, 150, 180))
    box = (1010, 470, 1150, 640)
    d.rounded_rectangle(box, 18, fill=(38, 92, 170))  # the mug
    d.arc((1120, 510, 1200, 600), 270, 90, fill=(38, 92, 170), width=18)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    l, t, r, b = box
    outline = f"M 0 0 L {r - l} 0 L {r - l} {b - t} L 0 {b - t} Z"
    return out.getvalue(), Mask("mug", box, 0.91, ((l + r) / 2, (t + b) / 2), (r - l) * (b - t), outline, (1.0, 1.0))


def show(state: ScreenState, scene: str) -> None:
    state.clear()
    state.new_turn()
    state.reminder_next("Call Sam", time.time() + 25 * 60)
    state.keeping(["keys: seen 2 hours ago, to my left", "glasses: seen 10 minutes ago, a little to my right",
                   "remote: seen 25 minutes ago, behind me on my left"],
                  [{"label": "keys", "yaw": 48.0, "pitch": 20.0, "ago_s": 7300},
                   {"label": "glasses", "yaw": -22.0, "pitch": 14.0, "ago_s": 600},
                   {"label": "remote", "yaw": 125.0, "pitch": 26.0, "ago_s": 1500}])
    state.doing("Waiting")
    state.said("")
    if scene == "finding":
        state.looking("mug")
        state.timer_start()
        state._timer = (time.monotonic() - 3.2, None)  # a search a few seconds in, for the picture
        state.said("Let me look.", "device", "fixed search on this computer")
        state.doing("Working", "Looking around the room")
        state.step("recall: no recent sighting")
        state.step("look: a little to my left, a little to my right")
    elif scene == "found":
        state.looking("mug")
        state.timer_start()
        for s in ("look: a little to my left, a little to my right", "compare: the blue one, next to the laptop",
                  "look closer and point: confirmed, a little to my right"):
            state.step(s)
        state.timer_stop()
        state._timer = (time.monotonic() - 9.4, time.monotonic())  # a typical find on the robot, for the picture
        jpeg, mask = sample_frame()
        found = Found("mug", -6.0, 14.0, 0.91, Frame(jpeg, 1920, 1080, -6.0, 14.0), mask, looks=3)
        state.found(found, "I see your blue mug, a little to my right.")
        state.said("I see your blue mug, a little to my right.", "device",
                   "search planned by Muse Glimmer on this computer")
        state.doing("Pointing", "At your mug")
        for name, times in (("Omnilingual ASR (hearing)", 1), ("Muse Glimmer (plans)", 2), ("SAM 3.1", 3),
                            ("Muse Glimmer (picture check)", 2), ("Kokoro (voice)", 1)):
            state.used(name, "device", times)
    elif scene == "answer":
        state.answered("Sunny tomorrow, with a high of 61 and a light breeze in the afternoon. That's according to "
                       "weather.gov.", [("Forecast for your area", "https://forecast.weather.gov/sample"),
                                         ("Hourly forecast", "https://www.weather.gov/sample-hourly")],
                       "cloud", "web search (Muse Spark)")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
        state.used("Muse Spark + web search", "cloud")
        state.sent("Muse Spark + web search", "what's the weather tomorrow? (home: Sunny Isles Beach, Florida)")
    elif scene == "drawing":
        state.drawn(SAMPLE_DRAWING.read_bytes(), "a lighthouse at dawn, in soft watercolor",
                    "Saved in Pictures, Andy, as andy-2026-10-27-191724.webp")
        state.said("Here's your picture, on the screen. I've saved it in your Pictures folder.", "cloud",
                   "a picture from your words (Muse Image)")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
        state.used("Muse Image", "cloud")
        state.sent("Muse Image", "a lighthouse at dawn, in soft watercolor")
    elif scene == "memory":
        state.remember_list(["keys: seen 2 hours ago, to my left", "glasses: seen 10 minutes ago, a little to my right",
                             "remote: seen 25 minutes ago, behind me on my left"])
        state.said("I'm keeping an eye on your keys and your glasses. It's on the screen.", "device")
        state.doing("Speaking", "Looking at you")
    elif scene == "help":
        state.show_help()
        state.said("I can find things and point at them, keep an eye on things, remind you, and look things up.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", nargs="?", default="found", choices=SCENES)
    ap.add_argument("--cycle", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--public", action="store_true", help="the hosted demo: per-visitor scenes, framed only by huggingface.co")
    args = ap.parse_args()
    state = ScreenState()
    if args.public:
        def snapshot(scene):
            st = ScreenState()
            show(st, scene)
            return st.snapshot()

        serve(state, host=args.host, port=args.port, frame_ancestors="https://huggingface.co https://*.hf.space",
              scenes={name: functools.partial(snapshot, name) for name in SCENES})
        print(f"public demo on http://{args.host}:{args.port}")
        while True:
            time.sleep(3600)
    serve(state, host=args.host, port=args.port)
    print(f"http://127.0.0.1:{args.port}  ·  Ctrl-C to stop")
    try:
        while True:
            for scene in (SCENES if args.cycle else [args.scene]):
                show(state, scene)
                time.sleep(8 if args.cycle else 3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
