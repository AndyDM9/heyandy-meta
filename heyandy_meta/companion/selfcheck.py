"""Andy checks itself: "Hey Andy, are you OK?"

For someone who lives alone with a robot, the worst moment isn't a lost key: it's Andy going quiet, and nobody knowing
whether it's broken, or what to tell whoever comes to help. So Andy checks each part it needs, through the same objects
it uses every turn (nothing extra runs), times each, and says in plain words what works, what doesn't, and what that
means for what it can still do; the TV shows the list. Nothing leaves the house: the camera's one frame goes to SAM 3.1
on this computer only, and the cloud is only said to be set up or not, never called.
"""
import io
import shutil
import time
import urllib.request
from dataclasses import dataclass, field

from ..robot.audio_watch import FIX


@dataclass
class Part:
    key: str
    name: str  # as Andy says it: "my camera"
    model: str = ""  # the Meta model doing it, if one does
    status: str = "ok"  # ok | warn | down | none (not set up here)
    detail: str = ""  # "180 ms"; "it's dark in here"
    if_down: str = ""  # what it means, said when it's down
    ms: float | None = None


@dataclass
class Report:
    parts: list[Part] = field(default_factory=list)
    seconds: float = 0.0

    def down(self) -> list[Part]:
        return [p for p in self.parts if p.status == "down"]

    def warn(self) -> list[Part]:
        return [p for p in self.parts if p.status == "warn"]


def ping(url: str, timeout: float = 3.0) -> float:
    """A local service's health, answered: how long it took, in ms."""
    started = time.monotonic()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        r.read(256)
    return (time.monotonic() - started) * 1000


def _timed(part: Part, fn) -> Part:
    started = time.monotonic()
    try:
        extra = fn()
        part.ms = round((time.monotonic() - started) * 1000)
        part.detail = extra or f"{part.ms} ms"
    except (OSError, TimeoutError) as e:  # a service that doesn't answer (URLError is an OSError)
        part.status, part.detail = "down", "not answering" if not isinstance(e, PermissionError) else type(e).__name__
    except Exception as e:  # noqa: BLE001 - a part that fails is a line in the list, not a crash
        part.status, part.detail = "down", str(e)[:40] or type(e).__name__
    return part


def brightness(jpeg: bytes) -> float:
    """The picture's mean brightness, 0 to 255, from a small decode (only a number is kept)."""
    from PIL import Image

    img = Image.open(io.BytesIO(jpeg))
    img.draft("L", (160, 90))
    small = img.convert("L").resize((160, 90))
    return sum(small.getdata()) / (160 * 90)


def check(app) -> Report:
    """Each part Andy needs, in the order a find uses them."""
    started, report = time.monotonic(), Report()
    body, frame = app.body, None

    def camera():
        nonlocal frame
        frame = body.capture()
        if not frame.image:
            return "the pretend room's camera" if hasattr(body, "room") else "no picture"
        b = brightness(frame.image)
        if b < 45:
            cam.status = "warn"
            return "it's dark in here"
        return None

    cam = Part("camera", "my camera", if_down="I can't see, so I can't find things. Please check my camera's cable, or restart me.")
    report.parts.append(_timed(cam, camera))
    if frame is not None and frame.image is not None:
        report.parts.append(_timed(Part("seeing", "recognising things", "SAM 3.1",
                                        if_down="I can't recognise things right now, so I can't find them. Restarting the computer beside me usually fixes it."),
                                   lambda: (app.segmenter.find(frame, "table"), None)[1]))
    else:
        report.parts.append(Part("seeing", "recognising things", "SAM 3.1", "down", "no picture to look at",
                                 "I can't recognise things without my camera."))

    def service(key, name, model, url, if_down):
        if url is None:
            return Part(key, name, model, "none", "not set up here")
        return _timed(Part(key, name, model, if_down=if_down), lambda: (ping(url), None)[1])

    endpoint = lambda thing, path: (getattr(thing, "endpoint", None) + path) if getattr(thing, "endpoint", None) else None  # noqa: E731
    report.parts.append(service("distance", "telling how far", "MapAnything", endpoint(app.depth, "/health"),
                                "I can still find things and point, but not say how far."))
    report.parts.append(service("thinking", "thinking", "Muse Glimmer", endpoint(app.device, "/models"),
                                "I can still find things, but not plan a search, check a picture or translate."))
    report.parts.append(service("voice", "hearing and speaking", "Omnilingual ASR, SeamlessM4T v2", endpoint(app.voice, "/health"),
                                "My hearing and voice aren't working; the TV still shows what I'd say."))
    report.parts.append(service("safety", "my safety check", "Llama Guard 3", endpoint(app.guard, "/health"),
                                "My second safety check isn't answering; the first, built in, still works."))

    ear, watch = getattr(app, "ear", None), getattr(app, "audio_watch", None)
    if watch is not None and watch.check():  # the robot's USB audio: what the kernel, the microphones and DoA say
        report.parts.append(Part("ears", "my microphones and speaker", "", "down", "stopped answering",
                                 f"I may not hear you, or be heard. Fix: {FIX}."))
    elif ear is None:
        report.parts.append(Part("ears", "my microphones", "", "none", "not listening here"))
    else:
        heard = ear.since(ear.clock() - 5.0)
        report.parts.append(Part("ears", "my microphones", "", "ok" if heard else "warn",
                                 "hearing the room" if heard else "nothing heard for a few seconds",
                                 "I may not hear you. Is my microphone covered?"))

    def moving():
        yaw, pitch = getattr(body, "yaw", 0.0), getattr(body, "pitch", 0.0)
        body.look(yaw + 8.0, pitch, precise=False)
        moved = getattr(body, "yaw", yaw + 8.0) - yaw
        body.look(yaw, pitch, precise=False)
        if abs(moved - 8.0) > 4.0:
            raise RuntimeError(f"turned {moved:.0f} of 8 degrees")
        return f"turned 8°, measured {moved:.1f}°"

    report.parts.append(_timed(Part("moving", "turning my head", if_down="I can't turn my head. Is the robot switched on?"), moving))

    def memory():
        folder = app.places.path.parent
        probe = folder / ".selfcheck"
        probe.write_text("ok")
        probe.unlink()
        free = shutil.disk_usage(folder).free / 1e9
        if free < 0.5:
            mem.status = "warn"
            return f"{free:.1f} GB free"
        return f"{free:.0f} GB free"

    mem = Part("memory", "remembering where things are", if_down="I can't write down where things are; my disk may be full.")
    report.parts.append(_timed(mem, memory))
    report.parts.append(Part("cloud", "the cloud", "Muse Spark",
                             "ok" if app.cloud is not None and app.online else "none",
                             "words only; not called now" if app.cloud is not None and app.online
                             else "off: I work without it"))
    report.seconds = round(time.monotonic() - started, 1)
    return report


CAN = {"camera": "see", "seeing": "recognise things", "distance": "tell how far", "thinking": "think",
       "voice": "hear and speak", "moving": "move"}


def summary(report: Report) -> str:
    """What Andy says: fine, or what's wrong and what it can still do."""
    down, warn = report.down(), report.warn()
    if not down:
        can = [CAN[p.key] for p in report.parts if p.key in CAN and p.status in ("ok", "warn")]
        last = ", and " if any(" and " in c for c in can[:-1]) else " and "  # "hear and speak, and move"
        said = (f"I'm fine, thanks for asking! I can {', '.join(can[:-1]) + last + can[-1] if len(can) > 1 else can[0]}, "
                f"all on this computer; that took {report.seconds:.0f} seconds to check.")
        if any(p.key == "camera" for p in warn):
            said += " It's a bit dark in here, so I'll find things better with a light on."
        if any(p.key == "ears" for p in warn):
            said += " I haven't heard much for a few seconds: is my microphone covered?"
        return said
    n = len(down)
    said = f"Mostly fine, but {n} thing{'s' if n > 1 else ''} {'aren' if n > 1 else 'isn'}'t working."
    for p in down[:2]:
        said += f" {p.name[0].upper() + p.name[1:]}{f' ({p.model})' if p.model else ''}: {p.if_down}"
    if n > 2:
        said += " The rest is on the screen."
    return said
