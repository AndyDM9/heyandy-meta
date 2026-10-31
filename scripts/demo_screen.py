"""Andy's TV page on sample data: no robot, no camera, no models. The picture is drawn here, not taken in a home.

    uv run python scripts/demo_screen.py found        # then open http://127.0.0.1:8765
    uv run python scripts/demo_screen.py --cycle      # every scene in turn, 8 s each
    python scripts/demo_screen.py --public --host 0.0.0.0 --port 7860   # the Hugging Face Space: each visitor picks
                                                                         # a scene; nothing they do reaches anyone else

Scenes: start, idle, finding, found, mine, cups, out, spanish, web, answer, drawing, memory, room, story, privacy, help.
"""
import argparse
import functools
import io
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heyandy_meta.finder.perspective import from_them  # noqa: E402
from heyandy_meta.finder.search import Found  # noqa: E402
from heyandy_meta.models.common import Mask  # noqa: E402
from heyandy_meta.robot.body import Frame  # noqa: E402
from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402

SCENES = ("start", "idle", "finding", "found", "mine", "cups", "out", "spanish", "web", "answer", "drawing", "memory", "room",
          "story", "privacy", "help")
SAMPLE_DRAWING = Path(__file__).resolve().parents[1] / "docs" / "images" / "sample-drawing.webp"  # made by Muse Image
SAMPLE_WEB = Path(__file__).resolve().parents[1] / "docs" / "images" / "sample-web.jpg"  # Wikipedia, CC BY-SA 4.0


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


CUPS = ((560.0, 1360.0), (960.0, 960.0), (1360.0, 560.0))  # where each cup started and ended: 0 and 2 swapped


@functools.lru_cache(maxsize=1)
def cups_frame() -> tuple[bytes, Mask]:
    """A drawn table with three identical red cups, after the shuffle, and the outline of the one with the ball."""
    img = Image.new("RGB", (1920, 1080), (196, 184, 168))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 560, 1920, 1080), fill=(139, 104, 74))
    for _, x in CUPS:
        d.polygon([(x - 90, 520), (x + 90, 520), (x + 65, 760), (x - 65, 760)], fill=(186, 34, 40))
        d.ellipse((x - 90, 500, x + 90, 540), fill=(226, 206, 200))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    x = CUPS[0][1]
    box = (int(x - 92), 500, int(x + 92), 762)
    outline = "M 2 0 L 182 0 L 157 262 L 27 262 Z"
    return out.getvalue(), Mask("cup", box, 0.93, (x, 640.0), 184 * 262, outline, (1.0, 1.0))


def sample_room() -> tuple[bytes, list[dict]]:
    """A made-up room's shape for the "room" scene, in Andy's axes (metres: x right, y down, z ahead, the camera at the
    middle), as int16 millimetres: a desk with a monitor and a keyboard, a sofa, the floor and two walls."""
    import random
    import struct

    rnd, pts = random.Random(4), []

    def plane(n, x0, x1, y0, y1, z0, z1):
        for _ in range(n):
            pts.append((rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(z0, z1)))

    plane(5200, -0.95, 0.95, 0.17, 0.18, 0.15, 1.15)      # the desk's top, just below Andy's camera
    plane(9000, -3.0, 3.0, 0.94, 0.95, -1.0, 3.4)         # the floor
    plane(5200, -3.0, 3.0, -1.3, 0.95, 3.39, 3.4)         # the wall ahead
    plane(3200, -3.0, -2.99, -1.3, 0.95, -1.0, 3.4)       # the wall on the left
    plane(1500, -0.62, 0.05, -0.32, 0.12, 0.98, 1.0)      # the monitor
    plane(700, 0.1, 0.55, 0.15, 0.16, 0.55, 0.72)         # the keyboard
    plane(2600, -2.4, -1.2, 0.45, 0.47, 1.7, 2.6)         # the sofa's seat
    plane(1600, -2.4, -1.2, 0.0, 0.46, 2.58, 2.6)         # and its back
    for x0, x1 in ((-0.9, -0.85), (0.85, 0.9)):           # the desk's legs
        plane(260, x0, x1, 0.18, 0.94, 1.05, 1.1)
    mm = [max(-32000, min(32000, round(v * 1000))) for p in pts for v in p]
    things = [{"label": "keys", "point": [0.24, 0.16, 0.48], "metres": 0.56, "views": 3, "yaw": -26.6, "pitch": 16.6},
              {"label": "cup", "point": [0.42, 0.12, 0.86], "metres": 0.96, "views": 2, "yaw": -26.0, "pitch": 7.2},
              {"label": "glasses", "point": [-0.3, 0.16, 0.72], "metres": 0.8, "views": 3, "yaw": 22.6, "pitch": 11.6},
              {"label": "remote", "point": [-1.7, 0.44, 2.1], "metres": 2.74, "views": 2, "yaw": 39.0, "pitch": 9.3}]
    return struct.pack(f"<{len(mm)}h", *mm), things


def show(state: ScreenState, scene: str) -> None:
    state.clear()
    state.new_turn()
    state.reminder_next("Call Sam", time.time() + 25 * 60)
    state.keeping(["keys: seen 2 hours ago, to my left", "glasses: seen 10 minutes ago, a little to my right",
                   "remote: seen 25 minutes ago, behind me on my left"],
                  [{"label": "keys", "yaw": 48.0, "pitch": 20.0, "ago_s": 7300, "metres": 1.7},
                   {"label": "glasses", "yaw": -22.0, "pitch": 14.0, "ago_s": 600, "metres": 0.9},
                   {"label": "remote", "yaw": 125.0, "pitch": 26.0, "ago_s": 1500, "metres": 2.6}])
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
        jpeg, mask = sample_frame()
        state.glimpse(Frame(jpeg, 1920, 1080, -6.0, 14.0), [mask])  # what Andy sees as it looks
    elif scene == "found":
        state.looking("mug")
        state.timer_start()
        for s in ("look: a little to my left, a little to my right", "compare: the blue one, next to the laptop",
                  "look closer and point: confirmed, a little to my right",
                  "checked: pointing at it, 1° off the middle", "MapAnything: 1.2 m away"):
            state.step(s)
        state.timer_stop()
        state._timer = (time.monotonic() - 9.4, time.monotonic())  # a typical find on the robot, for the picture
        jpeg, mask = sample_frame()
        found = Found("mug", -6.0, 14.0, 0.91, Frame(jpeg, 1920, 1080, -6.0, 14.0), mask, looks=3, aim_deg=1.0, metres=1.2)
        found.for_you = from_them((25.0, 5.0, 2.2), (found.yaw, found.pitch, found.metres))  # someone 2.2 m away, left of Andy
        words = f"There it is! I see your blue mug: {found.for_you['words']}, at your {found.for_you['clock']} o'clock."
        state.found(found, words)
        state.said(words, "device",
                   "search planned by Muse Glimmer on this computer")
        state.doing("Pointing", "At your mug")
        for name, times in (("Omnilingual ASR (hearing)", 1), ("Muse Glimmer (plans)", 2), ("SAM 3.1", 4),
                            ("Muse Glimmer (picture check)", 2), ("MapAnything (how far)", 1), ("SeamlessM4T v2 (voice)", 1)):
            state.used(name, "device", times)
    elif scene == "mine":
        state.looking("mug")
        state.timer_start()
        for s in ("look: a little to my left, a little to my right", "a mug, 58% like yours: not yours",
                  "a mug, 91% like yours: yours"):
            state.step(s)
        state.timer_stop()
        state._timer = (time.monotonic() - 11.2, time.monotonic())
        jpeg, mask = sample_frame()
        found = Found("mug", -6.0, 14.0, 0.91, Frame(jpeg, 1920, 1080, -6.0, 14.0), mask, looks=4, aim_deg=2.0, metres=1.2)
        words = "Found it! I see your mug, the one you showed me, a little to my right. The other mug isn't yours."
        state.found(found, words)
        state.said(words, "device", "fixed search on this computer")
        state.doing("Pointing", "At your mug")
        for name, times in (("Omnilingual ASR (hearing)", 1), ("SAM 3.1", 4), ("DINOv2 (knows it by sight)", 2),
                            ("Muse Glimmer (picture check)", 2), ("SeamlessM4T v2 (voice)", 1)):
            state.used(name, "device", times)
    elif scene == "cups":
        jpeg, mask = cups_frame()
        state.game("Replaying the shuffle", "SAM 3.1 is following every cup through 46 frames, on this computer.")
        trails = []
        for i, (a, b) in enumerate(CUPS):
            pts = [(a + (b - a) * t / 20, 640 + (60 if i == 0 else -60 if i == 2 else 0) * (1 - abs(10 - t) / 10))
                   for t in range(21)]
            trails.append((pts, i == 0))
        found = Found("cup", -18.0, 22.0, 0.93, Frame(jpeg, 1920, 1080, 0.0, 25.0), mask, looks=46)
        state.score = "Andy 2 · You 1"
        state.found(found, "I got it! Andy 2 · You 1", trails)
        state.said("Yes! I kept my eye on it. That's 2 to 1 to me. Again?", "device",
                   "SAM 3.1 followed every cup through 46 frames, on this computer (9 s)")
        state.doing("Pointing", "At the cup")
        state.used("SAM 3.1 Object Multiplex", "device", 46)
        state.used("Omnilingual ASR (hearing)", "device")
    elif scene == "out":
        state.going_out([{"thing": "keys", "here": True, "words": "Still here, on the desk, next to the lamp"},
                         {"thing": "glasses", "here": False, "words": "Not where I last saw them: with you?"},
                         {"thing": "remote", "here": False, "words": "Not where I last saw it: with you?"}],
                        "Take an umbrella: showers after 3, high near 82.", "")
        state.said("Don't forget your keys. I didn't see your glasses and your remote where I last saw them, so I hope "
                   "they're with you. Remember: at 9:39, call Sam. Take an umbrella. Have a lovely time!", "cloud",
                   "looked again where your things were last seen; the weather from the web")
        state.doing("Pointing", "At your keys")
        state.used("SAM 3.1", "device", 3)
        state.used("Muse Spark + web search", "cloud")
        state.sent("Muse Spark + web search", "Going out now: will I need an umbrella, a jacket or sun protection? "
                                              "(home: Sunny Isles Beach, Florida)")
    elif scene == "spanish":
        jpeg, mask = sample_frame()
        found = Found("mug", -6.0, 14.0, 0.91, Frame(jpeg, 1920, 1080, -6.0, 14.0), mask, looks=3, aim_deg=1.0, metres=1.2)
        state.language, state.lang = "Español · en esta computadora", "es"
        state.reminder_next("Llamar a Sam", time.time() + 25 * 60)
        state.keeping(["llaves: vistas hace 2 horas, a mi izquierda", "gafas: vistas hace 10 minutos, un poco a mi derecha",
                       "control remoto: visto hace 25 minutos, detrás de mí a la izquierda"],
                      [{"label": "llaves", "yaw": 48.0, "pitch": 20.0, "ago_s": 7300, "metres": 1.7},
                       {"label": "gafas", "yaw": -22.0, "pitch": 14.0, "ago_s": 600, "metres": 0.9},
                       {"label": "control remoto", "yaw": 125.0, "pitch": 26.0, "ago_s": 1500, "metres": 2.6}])
        state.looking("taza")
        state.timer_start()
        state.step("miré: un poco a mi izquierda, un poco a mi derecha")
        state.timer_stop()
        state._timer = (time.monotonic() - 8.1, time.monotonic())
        state.found(found, "Veo su taza azul, un poco a mi derecha.")
        state.said("Veo su taza azul, un poco a mi derecha.", "device", "búsqueda en esta computadora")
        state.doing("Pointing", "Señalando su taza")
        for name, times in (("Omnilingual ASR (hearing, Spanish)", 1), ("Muse Glimmer (translates)", 2), ("SAM 3.1", 3),
                            ("SeamlessM4T v2 (voice, Spanish)", 1)):
            state.used(name, "device", times)
    elif scene == "web":
        state.web(SAMPLE_WEB.read_bytes(), "Show me what banana bread is", "Opening the page", (378, 273),
                  url="https://en.wikipedia.org/wiki/Banana_bread")
        state.said("The TV is showing Wikipedia's page on banana bread: a sweet quick bread made from mashed bananas.",
                   "cloud", "Muse Spark used the web: screenshots of web pages, never the camera")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
        state.used("Muse Spark (web search)", "cloud")
        state.used("Muse Spark (computer use)", "cloud", 1)
        state.sent("Muse Spark (uses the web)", "show me what banana bread is on the TV")
        state.screenshots_sent("Muse Spark (computer use)", 1)
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
        state.remember_list(["keys: seen 2 hours ago, to my left, about 6 feet away",
                             "glasses: seen 10 minutes ago, a little to my right, about 3 feet away",
                             "remote: seen 25 minutes ago, behind me on my left, about 9 feet away"])
        state.said("I'm keeping an eye on your keys and your glasses. It's on the screen.", "device")
        state.doing("Speaking", "Looking at you")
    elif scene == "room":
        points, things = sample_room()
        state.room(points, things, 1.0)
        for line in ("looked to my right: cup, keys", "looked a little to my right: cup, glasses, keys",
                     "looked straight ahead: glasses, keys", "looked to my left: remote", "looked to my left: remote",
                     f"MapAnything: {len(points) // 6:,} points of shape in 1.0 s"):
            state.step(line)
        state.said("Here's the room as I measured it, on the screen: your keys a little to my right, about 2 feet away; "
                   "your glasses a little to my left, about 3 feet away; your cup a little to my right, about 3 feet "
                   "away. Its shape only, never a picture.", "device", "the room in 3D, measured on this computer")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
        state.used("SAM 3.1", "device", 5)
        state.used("MapAnything (the room in 3D)", "device")
    elif scene == "start":
        state.setup("things")
        state.said("Here's your room, measured in 3D. Now, what do you lose most often? Your keys, your glasses, your "
                   "phone, the remote?", "device", "getting started, on this computer")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
    elif scene == "story":
        state.timeline("keys", [
            {"when": "yesterday at 6:40", "how": "glanced", "words": "I saw them on the desk, behind the keyboard, in passing"},
            {"when": "at 8:12", "how": "found", "words": "I found them on the desk, behind the keyboard, about 2 feet away"},
            {"when": "at 10:42", "how": "noticed", "words": "You put them down on the shelf by the door"},
            {"when": "at 11:12", "how": "picked up", "words": "You picked them up."},
            {"when": "at 12:05", "how": "scanned", "words": "I saw them on the desk, behind the keyboard, measuring the room"}],
            {"words": "on the desk, behind the keyboard, about 2 feet away", "count": 4, "of": 6})
        state.said("Here's the story of your keys. At 8:12, I found them on the desk, behind the keyboard. At 10:42, you "
                   "put them down on the shelf by the door. At 11:12, you picked them up. At 12:05, I saw them on the "
                   "desk again. They usually end up on the desk, behind the keyboard. It's on the screen.", "device",
                   "from what Andy remembers, in words, on this computer")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
    elif scene == "privacy":
        state.privacy_day("21 of 24 requests stayed in this house",
                          [("✓", "21 requests answered on this computer: nothing sent"),
                           ("→", "Muse Spark: words from 3 requests"),
                           ("→", "68 words in all, each one shown on its turn's receipt"),
                           ("→", "2 screenshots of web pages you asked to see"),
                           ("✓", "No camera pictures and no sound left the house")])
        state.said("Today, 21 of your 24 requests stayed in this house. For the other 3, I sent 68 words to Muse Spark, "
                   "and 2 screenshots of web pages you asked to see. No camera pictures and no sound left the house. "
                   "It's on the screen.", "device", "counted on this computer from today's privacy receipts")
        state.doing("Speaking", "Looking at you")
        state.used("Omnilingual ASR (hearing)", "device")
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

        show(state, "room")  # the room's shape is fetched separately (room.bin): kept for every visitor
        state._room["until"] = float("inf")
        serve(state, host=args.host, port=args.port, frame_ancestors="https://huggingface.co https://*.hf.space", any_host=True,
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
