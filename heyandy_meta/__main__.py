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
import traceback

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

        body, segmenter = ReachyBody(), LocalSam31(args.sam)
        judge = GlimmerJudge(endpoint=args.glimmer, guard=segmenter.guard)  # Prompt Guard 2 reads notes in view too
        print(f"camera focus: held at {body.focus_at}" if body.focus_at is not None
              else "camera focus: left to the camera's autofocus", flush=True)
        if args.voice:
            from .voice.local import LocalVoice
            from .voice.speaker import Speaker

            body._say = Speaker(LocalVoice(args.voice_url, voice=args.voice_name), body.play)
            body.voice = body._say.voice
    else:
        room = Room(list(LIVING_ROOM))
        body, segmenter, judge = SimBody(room), SimSegmenter(room), SimJudge(room)
        body.say = lambda text: None  # the console prints instead
    andy = Andy(body, segmenter, device, places, reminders, ScreenState(), cloud, spark, judge,
                glimmer=None if args.no_local_agent else device.client, budget=budget, online=not args.offline,
                home=args.home)
    andy.voice = getattr(body, "voice", None)
    if args.robot and args.voice:  # the microphones' loudness, tone and direction, to turn to a ringing phone
        from .companion.sound import Ear

        andy.ear = Ear(head=lambda: body.yaw)
    andy.sounds = os.environ.get("HEYANDY_SOUNDS", "1") != "0"
    if args.voice:  # Spanish: Glimmer, on this computer, translates between the person and Andy's English rules
        from .companion.language import Translator

        andy.translator = Translator(args.glimmer)
    if args.robot:  # the second crisis check, on this computer (deploy/heyandy-guard.service); the word list if it's down
        from .companion.safety_model import GlimmerCheck, LlamaGuard

        andy.guard = LlamaGuard(args.guard)
        andy.second_look = GlimmerCheck(args.glimmer)  # a third look at conversation, for what no list has
        from .models.depth_local import LocalDepth

        andy.depth = LocalDepth(args.depth)  # how far away a found thing is (deploy/heyandy-depth.service)
    andy.load_voice()
    if args.staged_scene:
        if not args.robot:
            raise SystemExit("--staged-scene is for filming on the robot in a staged room")
        from .models.sam import Sam31Segmenter

        andy.use_staged_scene(Sam31Segmenter(budget=budget))
    return andy


def main() -> None:
    ap = argparse.ArgumentParser(prog="heyandy_meta")
    ap.add_argument("--robot", action="store_true", help="drive the Reachy Mini (default: a pretend living room)")
    ap.add_argument("--offline", action="store_true", help="act as if the network is down")
    ap.add_argument("--no-cloud", action="store_true", help="never call the Model API")
    ap.add_argument("--no-local-agent", action="store_true", help="don't let Glimmer plan searches (fixed sweep only)")
    ap.add_argument("--glimmer", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--guard", default="http://127.0.0.1:8094", help="Llama Guard 3, the second crisis check")
    ap.add_argument("--sam", default="http://127.0.0.1:8090")
    ap.add_argument("--voice", action="store_true", help="listen and speak through the robot (needs --robot)")
    ap.add_argument("--voice-url", default="http://127.0.0.1:8092")
    ap.add_argument("--depth", default="http://127.0.0.1:8096", help="MapAnything on this computer: how far away")
    ap.add_argument("--voice-name", default="eng", help="eng or spa (Meta's SeamlessM4T v2 voice)")
    ap.add_argument("--quiet", action="store_true", help="never print what was said (for running as a service)")
    ap.add_argument("--no-rest", action="store_true", help="never rest: keep breathing and looking for faces however "
                    "long nobody's there (companion/rest.py)")
    ap.add_argument("--home", default=os.environ.get("HEYANDY_HOME", ""),
                    help="where the person lives, e.g. 'Miami, Florida' (or HEYANDY_HOME), for the weather; never guessed")
    ap.add_argument("--staged-scene", action="store_true",
                    help="filming in a staged room only: the finder sends frames to SAM 3.1 through the Model API "
                         "(paid, and the TV says so); never in a lived-in home")
    ap.add_argument("--data", default="~/.local/share/heyandy-meta")
    ap.add_argument("--tv-port", type=int, default=8765)
    ap.add_argument("--remote", action="store_true",
                    help="let paired phones on the home network ask Andy from any room (screen/remote.py); off by default")
    ap.add_argument("--remote-port", type=int, default=8766)
    ap.add_argument("--remote-host", default="", help="the address phones use (default: this computer's home-network address)")
    ap.add_argument("--tv-host", default="127.0.0.1",
                    help="where the TV page listens: this computer only (default), or a home-network address for a "
                         "smart TV; never a public one")
    args = ap.parse_args()
    try:
        andy = build(args)
    except Exception:  # noqa: BLE001 - the robot's SDK leaves threads running: exit, so the service starts again
        traceback.print_exc()
        sys.stdout.flush(), sys.stderr.flush()
        os._exit(1)
    from .models.common import is_local

    if not is_local(f"http://{args.tv_host}"):
        raise SystemExit(f"--tv-host must be this computer or a home-network address, not {args.tv_host}")
    serve(andy.screen, host=args.tv_host, port=args.tv_port)
    if args.remote:
        from .screen.remote import Pairing, home_address, serve_remote

        ip = args.remote_host or home_address()
        if ip is None:
            print("--remote: no home-network address found; phones can't reach Andy", file=sys.stderr)
        else:
            andy.pairing = Pairing(os.path.join(os.path.expanduser(args.data), "remote.json"))
            andy.remote_url = f"http://{ip}:{args.remote_port}"
            serve_remote(andy.screen, andy.pairing, andy.ask_from_phone, ip, args.remote_port)
            print(f"Phones on the home network: {andy.remote_url} (say \"Andy, connect my phone\")")
    print(f"TV page: http://{args.tv_host}:{args.tv_port}  ·  Muse Spark: {'on' if andy.spark else 'off'}  ·  "
          f"{'robot' if args.robot else 'pretend living room'}  ·  Ctrl-D to quit")
    stop = threading.Event()

    def ticks():
        while not stop.wait(10):
            try:
                andy.tick()
            except Exception as e:  # noqa: BLE001 - one bad tick (a camera frame that didn't come) must not end
                print(f"tick: {type(e).__name__}: {e}"[:200], file=sys.stderr, flush=True)  # reminders for good

    threading.Thread(target=ticks, daemon=True).start()
    if not args.offline:  # follow the real network: unplug it and Andy carries on, on this computer
        from .network import watch

        threading.Thread(target=watch, args=(andy.set_online, stop), daemon=True).start()
    if args.voice and args.robot:
        from .voice.listen import Endpointer
        from .voice.local import LocalVoice
        from .voice.loop import VoiceLoop

        def shown(text, reply):
            if reply is None:  # not for Andy: only how many words, never what was said
                print(f"(heard {text}; not for Andy)", flush=True)
                return
            m = loop.marks
            end = m.get("ended", loop.utterance_end)  # this turn's words (something said over it ends later)
            first = getattr(andy.body._say, "first_after", lambda t: None)(end)
            wait = f"[first word {first - end:.1f}s after the person stopped]" if first else ""
            if "heard" in m and "began" in m:  # where the time went: numbers only
                again = f", listened again {m['again'][1] - m['again'][0]:.1f}s" if m.get("again") else ""
                wait += f" [heard at {m['heard'] - end:.1f}s{again}, turn began at {m['began'] - end:.1f}s]"
            if args.quiet:  # a service: its output is kept in the journal, so timings only, never words
                print(f"turn answered {wait}", flush=True)
            else:
                print(f"\nheard> {text}\nandy> {reply}  {wait}", flush=True)

        loop = VoiceLoop(andy, on_heard=shown)
        from .companion.rest import Rest, check

        rest = andy.rest = Rest(after_s=float("inf") if args.no_rest else Rest().after_s, woke_at=andy.clock())
        ears = Endpointer()
        threading.Thread(target=loop.run, args=(andy.body.listen, LocalVoice(args.voice_url), ears, stop),
                         daemon=True).start()
        from .robot.audio_watch import AudioWatch

        # Its ears and voice, watched: November 2 they stopped for half an hour and nothing said so
        andy.audio_watch = AudioWatch(andy.body, on_change=andy.screen.trouble)
        threading.Thread(target=andy.audio_watch.watch, args=(stop,), daemon=True, name="audio-watch").start()

        def look_at_the_person():
            """During a conversation: SAM 3.1 finds the face and the head eases towards it."""
            from .companion.attention import follow_face

            talking = time.monotonic() <= loop.awake_until or ears.active or getattr(andy.body, "speaking", False)
            # Never during a search (it needs the camera and a still head); never waiting on a turn either: reading a
            # frame and easing the gaze don't get in the way of anything else.
            if (not talking or andy.body.motion.mode in ("searching", "thinking") or andy.following or andy.quiet()
                    or rest.resting):  # resting: only a change in the picture asks SAM (rest_when_nobody_is_there)
                return
            found = follow_face(andy.body, andy.segmenter)
            if found:
                andy.person = found
                andy.screen.gaze_at(*found)  # the TV's face looks at them too

        def keep_eyes_on_the_person():  # about once a second
            while not stop.wait(1.0):
                try:
                    look_at_the_person()
                except Exception:  # noqa: BLE001 - a missed glance is fine; the eyes must never stop for good
                    pass

        threading.Thread(target=keep_eyes_on_the_person, daemon=True).start()

        from .finder.geometry import pixel_to_angles
        from .memory.notice import Noticer

        noticer = Noticer(andy.body, andy.segmenter, andy.places, cam=andy.finder.cam)

        def notice_things():
            """V-JEPA 2: between turns, while Andy keeps an eye on something and someone is in view, it holds still and
            watches in 4 s clips for a thing put down or picked up (memory/notice.py). A turn comes first: hear() (and
            a reminder or a glance) interrupts the clip at once and takes the head back; an interrupted clip asks no
            model and changes no memory."""
            while not stop.wait(5.0):
                try:
                    busy = (time.monotonic() <= loop.awake_until or ears.active or loop.busy or andy.following
                            or andy.playing or andy.quiet() or getattr(andy.body, "speaking", False) or rest.resting)
                    if busy or not andy.places.watching() or not hasattr(andy.segmenter, "action"):
                        continue
                    frame = andy.body.grab()
                    people = [m for m in andy.segmenter.find(frame, "person") if (m.score or 0.0) >= 0.5]
                    if not people:
                        continue  # nobody there to put anything down
                    best = max(people, key=lambda m: m.score or 0.0)  # the TV's face looks at them: a direction only
                    andy.screen.gaze_at(*pixel_to_angles(*best.center, frame.yaw, frame.pitch,
                                                         andy.finder._cam(frame)))
                    del frame
                    cancel = andy.begin_noticing()
                    if cancel is None:  # a turn is running, or the body is busy
                        continue
                    try:
                        if stop.wait(0.5) or cancel.is_set():
                            continue
                        seen = noticer.watch_once(
                            cancelled=lambda c=cancel: c.is_set() or ears.active or loop.busy
                            or time.monotonic() <= loop.awake_until)
                    finally:
                        andy.end_noticing(cancel)
                    if seen and not cancel.is_set():
                        andy.noticed(seen)
                except Exception:  # noqa: BLE001 - a missed clip is fine; noticing must never stop Andy
                    pass

        threading.Thread(target=notice_things, daemon=True).start()

        def rest_when_nobody_is_there():
            """No turn for ten minutes and nothing going on: Andy rests (companion/rest.py), still and quiet. Every 3 s
            while it rests, the camera's picture is compared with the room's on the processor; only a change asks SAM
            3.1 for a person, and someone there wakes it, as does any turn."""
            while not stop.wait(3.0):
                try:
                    check(rest, andy, loop, ears)
                except Exception:  # noqa: BLE001 - a missed check is fine: the next is 3 s away
                    pass

        threading.Thread(target=rest_when_nobody_is_there, daemon=True, name="rest").start()
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
