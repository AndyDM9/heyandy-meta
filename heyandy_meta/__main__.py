"""Run Andy from a keyboard: type what you'd say, read what Andy says, watch the TV page.

    uv run python -m heyandy_meta                 # a pretend living room, no robot
    uv run python -m heyandy_meta --robot         # the Reachy Mini, local SAM 3.1 and Glimmer
    uv run python -m heyandy_meta --robot --voice # ... and talk to it: "Andy, where are my glasses?"

The TV page is at http://127.0.0.1:8765. Muse Spark is used when MODEL_API_KEY is set and HEYANDY_PAID_CALLS=1;
otherwise everything runs on this computer.
"""
import argparse
import os
import sys
import threading
import time

from .app import Andy
from .budget import Budget
from .companion.reminders import Reminders
from .memory.places import Places
from .models.local_meta import GlimmerModel
from .models.muse_spark import BASE_URL, MuseSparkModel
from .robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing
from .screen.server import serve
from .screen.state import ScreenState

LIVING_ROOM = [  # a staged room for the console: two mugs, glasses, and a picture of glasses on the TV
    Thing("glasses", -48.0, 22.0, size_px=70),
    Thing("glasses", 52.0, 5.0, size_px=90, on_screen=True),
    Thing("keys", 15.0, 28.0, size_px=50),
    Thing("mug", 35.0, 18.0, looks="white, by the window"),
    Thing("mug", -15.0, 20.0, looks="blue, next to the laptop"),
    Thing("remote", 100.0, 24.0, size_px=80),
    Thing("person", 0.0, -5.0, size_px=300),
]


def build(args) -> Andy:
    data = os.path.expanduser(args.data)
    places, reminders = Places(f"{data}/places.json"), Reminders(f"{data}/reminders.json")
    budget = Budget()
    spark = cloud = None
    if os.environ.get("MODEL_API_KEY") and not args.no_cloud:
        from openai import OpenAI

        spark = OpenAI(base_url=BASE_URL, api_key=os.environ["MODEL_API_KEY"])
        cloud = MuseSparkModel(client=spark, budget=budget)
    device = GlimmerModel(endpoint=args.glimmer)
    if args.robot:
        from .finder.judge import GlimmerJudge
        from .models.sam_local import LocalSam31
        from .robot.reachy_mini import ReachyBody

        body, segmenter, judge = ReachyBody(), LocalSam31(args.sam), GlimmerJudge(endpoint=args.glimmer)
        if args.voice:
            from .voice.local import LocalVoice
            from .voice.speaker import Speaker

            body._say = Speaker(LocalVoice(args.voice_url, voice=args.voice_name), body.play)
    else:
        room = Room(list(LIVING_ROOM))
        body, segmenter, judge = SimBody(room), SimSegmenter(room), SimJudge(room)
        body.say = lambda text: None  # the console prints instead
    return Andy(body, segmenter, device, places, reminders, ScreenState(), cloud, spark, judge,
                glimmer=None if args.no_local_agent else device.client, budget=budget, online=not args.offline)


def main() -> None:
    ap = argparse.ArgumentParser(prog="heyandy_meta")
    ap.add_argument("--robot", action="store_true", help="drive the Reachy Mini (default: a pretend living room)")
    ap.add_argument("--offline", action="store_true", help="act as if the network is down")
    ap.add_argument("--no-cloud", action="store_true", help="never call the Model API")
    ap.add_argument("--no-local-agent", action="store_true", help="don't let Glimmer plan searches (fixed sweep only)")
    ap.add_argument("--glimmer", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--sam", default="http://127.0.0.1:8090")
    ap.add_argument("--voice", action="store_true", help="listen and speak through the robot (needs --robot)")
    ap.add_argument("--voice-url", default="http://127.0.0.1:8092")
    ap.add_argument("--voice-name", default="am_michael", help="a Kokoro voice")
    ap.add_argument("--data", default="~/.local/share/heyandy-meta")
    ap.add_argument("--tv-port", type=int, default=8765)
    args = ap.parse_args()
    andy = build(args)
    serve(andy.screen, port=args.tv_port)
    print(f"TV page: http://127.0.0.1:{args.tv_port}  ·  Muse Spark: {'on' if andy.spark else 'off'}  ·  "
          f"{'robot' if args.robot else 'pretend living room'}  ·  Ctrl-D to quit")
    stop = threading.Event()

    def ticks():
        while not stop.wait(10):
            andy.tick()

    threading.Thread(target=ticks, daemon=True).start()
    if args.voice and args.robot:
        from .voice.listen import Endpointer
        from .voice.local import LocalVoice
        from .voice.loop import VoiceLoop

        def shown(text, reply):  # only speech for Andy reaches here
            first = getattr(andy.body._say, "first_after", lambda t: None)(loop.utterance_end)
            wait = f"  [first word {first - loop.utterance_end:.1f}s after you stopped]" if first else ""
            print(f"\nheard> {text}\nandy> {reply}{wait}", flush=True)

        loop = VoiceLoop(andy, on_heard=shown)
        threading.Thread(target=loop.run, args=(andy.body.listen, LocalVoice(args.voice_url), Endpointer(), stop),
                         daemon=True).start()
        print("Listening: say \"Andy, ...\"")
    if args.voice and not sys.stdin.isatty():
        stop.wait()  # voice only: no keyboard attached
    try:
        while True:
            text = input("you> ").strip()
            if text:
                start = time.monotonic()
                reply = andy.hear(text)
                print(f"andy> {reply}  [{andy.screen.source or '-'}: {andy.screen.reason or '-'}, "
                      f"{time.monotonic() - start:.1f}s]")
    except (EOFError, KeyboardInterrupt):
        stop.set()
        print()


if __name__ == "__main__":
    main()
