"""Under the hood: each turn timed live, stage by stage, and which of Meta's models did each stage and where.

Andy's turns are physical: hearing (Omnilingual ASR), the head turning, the camera, SAM 3.1 at each look, Glimmer's
picture check, MapAnything measuring, the voice (SeamlessM4T v2). Each of those is timed as it runs, through thin
wrappers around the objects that do them (Timed), and kept per turn: which stage, when it started and ended from the
end of the person's words, and the model's name. Only numbers and names, in memory, the last few turns: never a word
said or a picture (the TV's /hood page; screen/server.py).
"""
import threading
import time
from collections import deque
from contextlib import contextmanager

# stage -> (what it is, the Meta model doing it, where it runs)
STAGES = {
    "hear": ("Hearing", "Omnilingual ASR", "on this computer"),
    "safety": ("Safety check", "Llama Guard 3", "on this computer"),
    "think": ("Thinking", "Muse Glimmer", "on this computer"),
    "plan": ("Planning the search", "Muse Glimmer", "on this computer"),
    "move": ("Head and base", "the robot's motors", "the robot"),
    "camera": ("Camera", "the robot's camera", "the robot"),
    "see": ("Seeing", "SAM 3.1", "on this computer"),
    "know": ("Knowing it by sight", "DINOv2", "on this computer"),
    "notice": ("Noticing", "V-JEPA 2", "on this computer"),
    "check": ("Checking the picture", "Muse Glimmer", "on this computer"),
    "measure": ("How far", "MapAnything", "on this computer"),
    "speak": ("Speaking", "SeamlessM4T v2", "on this computer"),
}
META_STAGES = {"hear", "safety", "think", "plan", "see", "know", "notice", "check", "measure", "speak"}  # Meta's models
CLOUD = {"Muse Spark", "Muse Image"}  # through the Meta Model API: words only


def _where(model: str) -> str:
    return "Meta Model API" if model in CLOUD else "on this computer"


KINDS = {"find": "a search", "follow": "following a thing", "guide": "guiding a hand", "sound": "a ringing",
         "room": "the room in 3D", "chat": "a conversation", "home_check": "a home check", "self_check": "a self-check",
         "tell": "remembering", "world": "a question about the world", "web": "the web", "game": "the cup game",
         "going_out": "going out", "describe": "looking", "time": "the time"}


class Hood:
    def __init__(self, clock=time.monotonic, keep: int = 12):
        self.clock, self._lock = clock, threading.RLock()
        self._turns: deque = deque(maxlen=keep)
        self._turn: dict | None = None
        self._heard: tuple[float, float] | None = None  # (when the person stopped speaking, how long hearing took)
        self._sound_before: float | None = None  # Andy's "heard" note, played before the turn begins
        self._before: list[tuple] = []  # stages run after the words and before the turn: (stage, started, ended, model)
        self._live: dict[int, tuple] = {}  # Meta model calls running now: id -> (stage, model, started)
        self._done: deque = deque(maxlen=8)  # the latest finished: (stage, model, started, ended)
        self._ids = 0
        self.since = {"turns": 0, "see": 0, "camera": 0, "measure": 0, "check": 0, "plan": 0, "think": 0, "speak": 0,
                      "move": 0, "know": 0, "notice": 0, "started": time.time()}

    def heard(self, words_ended: float, hearing_s: float) -> None:
        """The voice loop: the person's words ended at words_ended (this clock), and hearing them took hearing_s."""
        with self._lock:
            self._heard = (words_ended, hearing_s)
            now = self.clock()
            self._done.append(("hear", STAGES["hear"][1], now - hearing_s, now))

    def heard_again(self, started: float, ended: float) -> None:
        """The voice loop listened again, told no language (did they speak another of Andy's?): before the turn
        begins, so it's kept and joins the turn's timeline when it does."""
        with self._lock:
            if self._turn is None:
                self._before = (self._before + [("hear", started, ended, "again")])[-4:]
            self._done.append(("hear", STAGES["hear"][1], started, ended))

    def calling(self, stage: str, model: str) -> int:
        """A call starting, for the TV's live strip; returns its id for done()."""
        with self._lock:
            self._ids += 1
            self._live[self._ids] = (stage, model, self.clock())
            return self._ids

    def done(self, call: int) -> None:
        with self._lock:
            stage, model, started = self._live.pop(call, (None, None, None))
            if stage is not None:
                self._done.append((stage, model, started, self.clock()))

    def calls(self, keep_s: float = 20.0) -> dict:
        """The TV's "Meta, live" strip: Meta's models working now (with how long so far) and the last few that just
        finished (and how long they took), each with where it runs. The robot's own motors and camera aren't in it."""
        with self._lock:
            now = self.clock()
            meta = lambda stage: stage in META_STAGES  # noqa: E731
            live = [{"stage": st, "model": m or STAGES[st][1], "where": _where(m or STAGES[st][1]), "s": round(now - t0, 1)}
                    for st, m, t0 in self._live.values() if meta(st)]
            done = [{"stage": st, "model": m or STAGES[st][1], "where": _where(m or STAGES[st][1]), "s": round(t1 - t0, 2),
                     "ago": round(now - t1, 1)} for st, m, t0, t1 in self._done if meta(st) and now - t1 <= keep_s]
        return {"live": live, "done": done[::-1][:5]}

    def begin(self) -> None:
        with self._lock:
            now = self.clock()
            heard, self._heard = self._heard, None
            t0 = heard[0] if heard and now - heard[0] < 30 else now  # from the end of the words, when Andy heard them
            early, self._sound_before = self._sound_before, None
            self._turn = {"t0": t0, "kind": "", "spans": [],
                          "first_sound": round(early - t0, 2) if early is not None and t0 <= early <= now else None}
            if heard and t0 < now:
                self._turn["spans"].append(["hear", 0.0, round(max(0.0, min(heard[1], now - t0)), 2), ""])
            before, self._before = self._before, []
            for stage, a, b, model in before:
                if t0 <= a <= b <= now:
                    self._turn["spans"].append([stage, round(a - t0, 2), round(b - t0, 2), model])

    def kind(self, kind: str) -> None:
        with self._lock:
            if self._turn is not None:
                self._turn["kind"] = kind

    def sound(self) -> None:
        """Andy's first sound this turn (the "heard" note, or its first word)."""
        with self._lock:
            if self._turn is None:
                if self._heard is not None:
                    self._sound_before = self.clock()  # the "heard" note: before the turn, after the words
            elif self._turn["first_sound"] is None:
                self._turn["first_sound"] = round(self.clock() - self._turn["t0"], 2)

    def end(self) -> None:
        with self._lock:
            t = self._turn
            if t is None:
                return
            self._turn = None
            t["total"] = round(self.clock() - t["t0"], 2)
            self._turns.append(t)
            self.since["turns"] += 1

    @contextmanager
    def span(self, stage: str, model: str = ""):
        start, call = self.clock(), self.calling(stage, model)
        try:
            yield
        finally:
            self.done(call)
            self._record(stage, start, self.clock(), model)

    def _record(self, stage: str, start: float, end: float, model: str = "") -> None:
        with self._lock:
            if stage in self.since:
                self.since[stage] += 1
            t = self._turn
            if t is not None:
                t["spans"].append([stage, round(start - t["t0"], 2), round(end - t["t0"], 2), model])
                if stage == "speak":
                    self.sound()

    def wrap(self, obj, methods: dict[str, tuple[str, str]]):
        """obj, with the methods named timed: {method: (stage, model)}; everything else passes straight through."""
        return obj if obj is None or isinstance(obj, Timed) else Timed(obj, self, methods)

    def snapshot(self) -> dict:
        with self._lock:
            turns = [dict(t) for t in self._turns]
            since = dict(self.since)
        out = {"latest": None, "turns": [], "since": since, "stages": {k: list(v) for k, v in STAGES.items()}}
        for t in turns:
            per = {}
            for stage, a, b, _ in t["spans"]:
                per[stage] = round(per.get(stage, 0.0) + (b - a), 2)
            out["turns"].append({"kind": t["kind"], "what": KINDS.get(t["kind"], "a turn"), "total": t["total"],
                                 "stages": per, "first_sound": t["first_sound"],
                                 "spans": [[stage, a, b] for stage, a, b, _ in t["spans"]]})
        if turns:
            t = turns[-1]
            out["latest"] = {**out["turns"][-1], "spans": t["spans"]}
        return out


class Timed:
    """A stand-in for an object whose methods are timed as one stage of the turn: every attribute is the object's own
    (read and set straight through), and a call to one of its methods is recorded with when it ran."""

    def __init__(self, obj, hood: Hood, methods: dict[str, tuple[str, str]]):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_hood", hood)
        object.__setattr__(self, "_methods", methods)

    def __getattr__(self, name):
        value = getattr(self._obj, name)
        if name not in self._methods or not callable(value):
            return value
        hood, (stage, model) = self._hood, self._methods[name]

        def timed(*args, **kwargs):
            start, call = hood.clock(), hood.calling(stage, model)
            try:
                return value(*args, **kwargs)
            finally:
                hood.done(call)
                hood._record(stage, start, hood.clock(), model)

        return timed

    def __setattr__(self, name, value):
        setattr(self._obj, name, value)

    def __delattr__(self, name):
        delattr(self._obj, name)
