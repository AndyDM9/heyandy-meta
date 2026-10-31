"""What the TV shows: Andy's words, who answered, and the picture a thing was found in.

The picture lives only here, in memory, and is dropped after two minutes. Nothing on this page is saved.
"""
import base64
import datetime as dt
import threading
import time
from dataclasses import dataclass, field, replace

from ..finder.search import Found

PICTURE_SECONDS = 120
HELP_SECONDS = 60
DRAWING_SECONDS = 10 * 60
WEB_SECONDS = 10 * 60
ROOM_SECONDS = 120  # the room in 3D: shape only, in memory, gone after two minutes


@dataclass
class _Picture:
    jpeg: bytes
    found: Found
    words: str
    until: float
    trails: list | None = None  # the cup game: each cup's path through the shuffle, [(points, is_the_one)]


@dataclass
class Day:
    """What left the house today, as counts from the receipts (never the words themselves): for "what did you send
    today?". Kept in memory only, so it starts again when Andy does (since says when)."""
    date: dt.date
    since: float  # when counting began: midnight, or when Andy started, epoch seconds
    turns: int = 0  # finished turns
    went: int = 0  # of those, the turns that sent anything to a cloud model
    words: int = 0  # words sent, in all (earlier exchanges sent along with a request count again)
    to: dict = field(default_factory=dict)  # "Muse Spark" -> the turns it was sent something on
    screenshots: int = 0  # screenshots of web pages the person asked to see
    pictures: int = 0  # camera pictures of a staged scene (never a lived-in room)


def _family(model: str) -> str:
    """"Muse Spark (agent)" and "Muse Spark + web search" are both Muse Spark."""
    return model.split(" (")[0].split(" + ")[0]


class ScreenState:
    def __init__(self, clock=time.monotonic, now=time.time):
        self._clock, self._lock, self._now = clock, threading.Lock(), now
        self.caption = ""
        self.source, self.reason = "", ""
        self.online = True
        self._picture: _Picture | None = None
        self._glimpse: dict | None = None  # the latest frame of a search, with what SAM 3.1 found in it (memory only)
        self._glimpses = 0
        self.sources: list[tuple[str, str]] = []  # (title, url) under an answer
        self.steps: list[str] = []  # the plan as it happens: "look: right, far right"
        self.memory: list[str] | None = None  # shown while "what do you remember?" is answered
        self._timer: tuple[float, float | None] | None = None  # (started, stopped)
        self.models: dict[str, list] = {}  # this turn's Meta models: name -> [where, times used]
        self.outbox: list[dict] = []  # the privacy receipt: exactly what words went to which cloud model this turn
        self.state, self.head = "Waiting", ""  # the pill: what Andy is doing, and what its head is turned to
        self.looking_for = ""  # "your cup", while a search runs and after
        self.next_reminder: tuple[str, float] | None = None  # (the person's words, when), epoch seconds
        self.watching: list[str] = []  # what Andy keeps an eye on, and where it last saw each
        self.watching_map: list[dict] = []  # the same as directions, for the TV's map
        self._help_until = 0.0
        self.quiet_text = ""  # "Quiet until 9:40", while Andy keeps quiet
        self.language = ""  # "Español", while Andy hears and speaks Spanish
        self.lang = "en"  # the TV's own labels follow it (page.html)
        self.words = None  # Andy's own words on the TV, in that language: a TVWords, or None for English
        self._notice: tuple[str, float] | None = None  # a short notice ("Volume ●●●●○○○"), and until when
        self.staged = False  # a staged scene: camera pictures go to the Model API, and the TV says so
        self._drawing: tuple[bytes, str, str, float] | None = None  # (WebP, what was asked, where it's saved, until)
        self.drawings = 0  # a version for the page, so it fetches each new picture once
        self._game: tuple[str, str, float] | None = None  # the cup game: (what's happening, the detail, until)
        self.score = ""  # "Andy 2 · You 1", for this session's cup games
        self.checklist: dict | None = None  # "I'm going out": each watched thing, still here or not; the weather
        self._web: dict | None = None  # the web page Andy is using: the screenshot, what's happening, where it clicks
        self.webs = 0  # a version, so the page fetches each screenshot once
        self.privacy: dict | None = None  # "what did you send today?": {"title", "rows": [{"mark", "text"}]}
        self._gaze: tuple[float, float, float] | None = None  # where the person is (yaw, pitch, when): a direction only
        self._setup: dict | None = None  # the guided first minutes: {"step", "thing", "until"}
        self._pairing: dict | None = None  # "connect my phone": {"url", "code", "until"} for three minutes
        self._timeline: dict | None = None  # a watched thing's story: {"thing", "items", "usual"}, words only
        self._room: dict | None = None  # the room in 3D: its shape (millimetres, int16 x, y, z), the things, until
        self.rooms = 0  # a version, so the page fetches each room once
        self._day = Day(dt.date.fromtimestamp(now()), now())
        self._in_turn = False

    def gaze_at(self, yaw: float, pitch: float) -> None:
        """Where Andy last saw the person, as a direction only: the TV's face looks that way (page.html, ambient)."""
        with self._lock:
            self._gaze = (yaw, pitch, self._clock())

    def doing(self, state: str, head: str = "") -> None:
        with self._lock:
            self.state, self.head = state, head

    def looking(self, thing: str) -> None:
        with self._lock:
            self._room = self._timeline = None  # whatever is shown next takes the room's place
            self.privacy = None
            self.looking_for, self._glimpse = thing, None

    def glimpse(self, frame, masks: list) -> None:
        """What Andy sees right now, while it searches: the frame and SAM 3.1's outlines, held in memory only and
        dropped when the search ends (as the found picture is). The pretend room has no camera: nothing to show."""
        if not getattr(frame, "image", None):
            return
        with self._lock:
            self._glimpses += 1
            self._glimpse = {"jpeg": frame.image, "width": frame.width, "height": frame.height, "v": self._glimpses,
                             "masks": [{"outline": m.outline, "box": list(m.box), "scale": list(m.outline_scale),
                                        "score": m.score} for m in masks[:6]]}

    def reminder_next(self, text: str | None, at: float = 0.0) -> None:
        with self._lock:
            self.next_reminder = (text, at) if text else None

    def keeping(self, lines: list[str], where: list[dict] | None = None) -> None:
        with self._lock:
            self.watching, self.watching_map = list(lines), list(where or [])

    def drawn(self, image: bytes, prompt: str, saved: str) -> None:
        with self._lock:
            self._room = self._timeline = None
            self.privacy = None
            self._picture, self.sources, self.steps, self.memory, self._timer, self.looking_for = None, [], [], None, None, ""
            self._drawing, self._web = (image, prompt, saved, self._clock() + DRAWING_SECONDS), None
            self.drawings += 1

    def web(self, jpeg: bytes, request: str, words: str = "", point=None, size=(1280, 800), url: str = "") -> None:
        """A screenshot of the web page Andy is using (never the camera), as each step happens."""
        with self._lock:
            self._room = self._timeline = None
            self.privacy = None
            self._picture, self._drawing, self.sources, self.memory, self._game = None, None, [], None, None
            before = self._web or {}
            self._web = {"jpeg": jpeg, "request": request, "words": words or before.get("words", ""),
                         "point": [point[0] / size[0], point[1] / size[1]] if point else None,
                         "host": url.split("/")[2].removeprefix("www.") if url.count("/") >= 2 else before.get("host", ""),
                         "until": self._clock() + WEB_SECONDS}
            self.webs += 1

    def going_out(self, items: list[dict], weather: str = "", next_up: str = "") -> None:
        """The going-out check: [{"thing", "here": True/False/None, "words"}], the weather and the next reminder."""
        with self._lock:
            self._room = self._timeline = None
            self.privacy = None
            self._picture, self._drawing, self._web, self._game, self.memory, self.sources = None, None, None, None, None, []
            self.checklist = {"items": list(items), "weather": weather, "next": next_up}

    def room(self, points_mm: bytes, things: list[dict], seconds: float = 0.0) -> None:
        """The room in 3D: its shape as millimetres (int16 x right, y down, z ahead, the robot's camera at the middle),
        never a colour or a picture, and the things in it [{"label", "point" (metres), "metres", "views"}]."""
        with self._lock:
            self.privacy, self.checklist, self.memory, self.sources = None, None, None, []
            self._picture, self._drawing, self._web, self._game = None, None, None, None
            self._timeline = None
            self._room = {"points": points_mm, "things": list(things), "seconds": seconds,
                          "until": self._clock() + ROOM_SECONDS}
            self.rooms += 1

    def setup(self, step: str | None, info: dict | None = None) -> None:
        """"Let's get started": which step the TV shows ("things", "try", "done"); None ends it."""
        with self._lock:
            self._setup = {"step": step, **(info or {}), "until": self._clock() + (120 if step == "done" else 300)} \
                if step else None

    def pairing(self, url: str, code: str, seconds: float) -> None:
        """The phone pairing card: where to go and the six numbers, until they run out (seconds 0: gone)."""
        with self._lock:
            self._pairing = {"url": url, "code": code, "until": self._clock() + seconds} if code and seconds > 0 else None

    def timeline(self, thing: str, items: list[dict], usual: dict | None = None) -> None:
        """"What happened to my keys?": where it has been, as Andy knew it (words, never a picture), for two minutes."""
        with self._lock:
            self.privacy, self.checklist, self.memory, self.sources = None, None, None, []
            self._picture, self._drawing, self._web, self._game, self._room = None, None, None, None, None
            self._timeline = {"thing": thing, "items": list(items), "usual": usual, "until": self._clock() + ROOM_SECONDS}

    def room_bytes(self) -> bytes | None:
        with self._lock:
            return self._room["points"] if self._room else None

    def web_bytes(self) -> bytes | None:
        with self._lock:
            return self._web["jpeg"] if self._web else None

    def drawing_bytes(self) -> bytes | None:
        with self._lock:
            return self._drawing[0] if self._drawing else None

    def quiet(self, text: str) -> None:
        with self._lock:
            self.quiet_text = text

    def notice(self, text: str, seconds: float = 6.0) -> None:
        """A change shown briefly, like a TV's own volume bar, then gone."""
        with self._lock:
            self._notice = (text, self._clock() + seconds)

    def show_help(self) -> None:
        with self._lock:
            self._room = self._timeline = None  # whatever is shown next takes the room's place
            self._help_until = self._clock() + HELP_SECONDS

    def new_turn(self) -> None:
        with self._lock:
            if self._in_turn:  # the turn before, counted for the day
                day = self._today()
                went = {_family(o["to"]) for o in self.outbox}
                day.turns, day.went = day.turns + 1, day.went + bool(went)
                for f in went:
                    day.to[f] = day.to.get(f, 0) + 1
            self._in_turn = True
            self.models, self.outbox = {}, []

    def _today(self) -> Day:
        """Today's counts (the lock is held): a new day starts them again, from midnight."""
        now = self._now()
        if dt.date.fromtimestamp(now) != self._day.date:
            date = dt.date.fromtimestamp(now)
            self._day = Day(date, dt.datetime.combine(date, dt.time()).timestamp())
        return self._day

    def day(self) -> Day:
        """What left the house today, over the finished turns (a copy)."""
        with self._lock:
            d = self._today()
            return replace(d, to=dict(d.to))

    def sent(self, model: str, words: str, earlier: int = 0) -> None:
        """Words that left the house this turn, and to which model (earlier: past exchanges sent along with them)."""
        with self._lock:
            self._today().words += len(words.split())
        words = words if len(words) <= 200 else words[:199] + "…"  # cut where the TV says so, never silently
        with self._lock:
            self.outbox.append({"to": model, "words": words, "earlier": earlier})

    def screenshots_sent(self, model: str, n: int) -> None:
        """Screenshots of web pages that left the house this turn (for "show me ... on the TV"), never the camera."""
        if n <= 0:
            return
        with self._lock:
            self._today().screenshots += n
            self.outbox.append({"to": model, "words": f"{n} screenshot{'s' if n != 1 else ''} of the web page",
                                "earlier": 0})

    def used(self, name: str, where: str = "device", times: int = 1) -> None:
        """A model worked on this turn: "device" (this computer) or "cloud" (words only)."""
        if times <= 0:
            return
        with self._lock:
            self.models.setdefault(name, [where, 0])[1] += times
            if name.startswith("SAM 3.1") and where == "cloud":  # a staged scene: camera pictures went, and the receipt says so
                self._today().pictures += times
                self.outbox.append({"to": "SAM 3.1 (Model API, staged scene)", "words": f"{times} camera pictures",
                                    "earlier": 0, "pictures": True})

    def said(self, text: str, source: str = "", reason: str = "") -> None:
        with self._lock:
            self.caption, self.source, self.reason = text, source, reason

    def found(self, found: Found, words: str, trails: list | None = None) -> None:
        with self._lock:
            self._glimpse = None  # the search is over
        if not found.frame.image:  # the pretend room has no camera: words only
            return
        with self._lock:
            self.privacy = None
            self._picture, self._web = _Picture(found.frame.image, found, words, self._clock() + PICTURE_SECONDS, trails), None
            self._room = self._timeline = None

    def game(self, title: str, detail: str = "") -> None:
        """The cup game, stage by stage: "Watching the cups", "Replaying the shuffle"."""
        with self._lock:
            self._room = self._timeline = None
            self.privacy = None
            self._picture, self._drawing, self.sources, self.steps, self.memory = None, None, [], [], None
            self._game, self._web = (title, detail, self._clock() + PICTURE_SECONDS), None

    def clear(self) -> None:
        with self._lock:
            self._picture, self.sources, self.steps, self.memory, self._timer = None, [], [], None, None
            self.looking_for, self._help_until, self._drawing, self._game, self._web = "", 0.0, None, None, None
            self.checklist, self.privacy = None, None
            self._glimpse = None  # the last frame of a search that found nothing goes too
            self._room = self._timeline = None

    def privacy_day(self, title: str, rows: list[tuple[str, str]]) -> None:
        """The answer to "what did you send today?" as a card, each row marked ✓ (stayed), → (went) or ! (camera
        pictures). Whatever is shown next takes its place."""
        with self._lock:
            self._room = self._timeline = None
            self._picture, self._drawing, self._web, self._game, self.memory, self.sources = None, None, None, None, None, []
            self.checklist = None
            self.privacy = {"title": title, "rows": [{"mark": m, "text": t} for m, t in rows]}

    def answered(self, text: str, sources: list[tuple[str, str]], source: str = "cloud", reason: str = "") -> None:
        with self._lock:
            self._room = self._timeline = None  # whatever is shown next takes the room's place
            self.privacy = None
            self.caption, self.source, self.reason, self.sources = text, source, reason, list(sources)[:3]
            self._web = None

    def step(self, line: str) -> None:
        with self._lock:
            self.steps = (self.steps + [line])[-6:]

    def remember_list(self, lines: list[str]) -> None:
        with self._lock:
            self._room = self._timeline = None  # whatever is shown next takes the room's place
            self.privacy = None
            self.memory = list(lines)

    def timer_start(self) -> None:
        with self._lock:
            self._timer, self.steps = (self._clock(), None), []

    def timer_stop(self) -> None:
        with self._lock:
            if self._timer and self._timer[1] is None:
                self._timer = (self._timer[0], self._clock())

    def snapshot(self) -> dict:
        with self._lock:
            if self._picture and self._clock() >= self._picture.until:
                self._picture = None
            out = {"caption": self.caption, "source": self.source, "reason": self.reason, "online": self.online,
                   "picture": None, "sources": [{"title": a, "url": b} for a, b in self.sources],
                   "steps": list(self.steps), "memory": self.memory, "seconds": None, "running": False,
                   "models": [{"name": n, "where": w, "times": t} for n, (w, t) in self.models.items()],
                   "state": self.state, "head": self.head, "looking_for": self.looking_for,
                   "next": {"text": self.next_reminder[0], "at": self.next_reminder[1]} if self.next_reminder else None,
                   "watching": list(self.watching), "map": list(self.watching_map),
                   "help": self._clock() < self._help_until,
                   "staged": self.staged, "drawing": None,
                   "quiet": self.quiet_text, "outbox": list(self.outbox), "language": self.language,
                   "notice": self._notice[0] if self._notice and self._clock() < self._notice[1] else "",
                   "game": None, "checklist": self.checklist, "privacy": self.privacy}
            if self._web and self._clock() >= self._web["until"]:
                self._web = None
            out["web"] = {"v": self.webs, **{k: v for k, v in self._web.items() if k not in ("jpeg", "until")}} \
                if self._web else None
            if self._game and self._clock() < self._game[2]:
                out["game"] = {"title": self._game[0], "detail": self._game[1], "score": self.score}
            if self._room and self._clock() >= self._room["until"]:
                self._room = None
            out["room"] = {"v": self.rooms, "things": self._room["things"], "n": len(self._room["points"]) // 6,
                           "seconds": self._room["seconds"]} if self._room else None
            if self._setup and self._clock() >= self._setup["until"]:
                self._setup = None
            out["setup"] = {k: v for k, v in self._setup.items() if k != "until"} if self._setup else None
            if self._pairing and self._clock() >= self._pairing["until"]:
                self._pairing = None
            out["pairing"] = {"url": self._pairing["url"], "code": self._pairing["code"],
                              "left": round(self._pairing["until"] - self._clock())} if self._pairing else None
            if self._timeline and self._clock() >= self._timeline["until"]:
                self._timeline = None
            out["timeline"] = {k: v for k, v in self._timeline.items() if k != "until"} if self._timeline else None
            if self._drawing and self._clock() >= self._drawing[3]:
                self._drawing = None
            if self._drawing:
                out["drawing"] = {"v": self.drawings, "prompt": self._drawing[1], "saved": self._drawing[2]}
            if self._timer:
                start, stop = self._timer
                out["seconds"] = round((stop if stop is not None else self._clock()) - start, 1)
                out["running"] = stop is None
            out["lang"] = self.lang
            if self._gaze and self._clock() - self._gaze[2] < 30:
                out["gaze"] = {"yaw": round(self._gaze[0], 1), "pitch": round(self._gaze[1], 1),
                               "age": round(self._clock() - self._gaze[2], 1)}
            g = self._glimpse
            if g and out.get("running"):  # only while a search runs; never after
                out["glimpse"] = {"src": "data:image/jpeg;base64," + base64.b64encode(g["jpeg"]).decode(),
                                  **{k: v for k, v in g.items() if k != "jpeg"}}
            p = self._picture
            if p:
                f, m = p.found, p.found.mask
                out["picture"] = {
                    "src": "data:image/jpeg;base64," + base64.b64encode(p.jpeg).decode(),
                    "width": f.frame.width, "height": f.frame.height,
                    "label": f.label, "words": p.words,
                    "outline": m.outline, "box": list(m.box), "scale": list(m.outline_scale),
                    "seconds_left": round(p.until - self._clock()),
                    # measured: how far off the middle of the view the point landed, and how far away (MapAnything)
                    "aim_deg": getattr(f, "aim_deg", None), "metres": getattr(f, "metres", None),
                    "for_you": getattr(f, "for_you", None),  # where it is from the person's side, and the plan
                }
                if p.trails:
                    out["picture"]["trails"] = [{"d": "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in pts),
                                                 "chosen": chosen} for pts, chosen in p.trails if len(pts) >= 2]
            words = self.words if self.lang != "en" else None
        return _in(out, words) if words else out


def _in(out: dict, tr) -> dict:
    """The snapshot with Andy's own words in the person's language (the caption already is; names of models aren't)."""
    for key in ("head", "looking_for"):
        out[key] = tr(out[key])
    out["steps"] = [tr(x) for x in out["steps"]]
    out["watching"] = [tr(x) for x in out["watching"]]
    if out["memory"] is not None:
        out["memory"] = [tr(x) for x in out["memory"]]
    out["map"] = [{**m, "label": tr(m["label"])} for m in out["map"]]
    if out["next"]:
        out["next"] = {**out["next"], "text": tr(out["next"]["text"])}
    if out["picture"]:
        out["picture"] = {**out["picture"], "words": tr(out["picture"]["words"]), "label": tr(out["picture"]["label"])}
    if out["game"]:
        out["game"] = {**out["game"], "title": tr(out["game"]["title"]), "detail": tr(out["game"]["detail"])}
    if out["checklist"]:
        c = out["checklist"]
        out["checklist"] = {**c, "weather": tr(c["weather"]), "next": tr(c["next"]),
                            "items": [{**i, "thing": tr(i["thing"]), "words": tr(i["words"])} for i in c["items"]]}
    if out["privacy"]:
        p = out["privacy"]
        out["privacy"] = {"title": tr(p["title"]), "rows": [{**r, "text": tr(r["text"])} for r in p["rows"]]}
    if out["web"]:
        out["web"] = {**out["web"], "request": tr(out["web"]["request"]), "words": tr(out["web"]["words"])}
    if out["drawing"]:
        out["drawing"] = {**out["drawing"], "prompt": tr(out["drawing"]["prompt"])}
    out["reason"] = tr(out["reason"])
    return out
