"""Andy, one turn at a time: from what the person said to what the robot does in the room and says.

Every turn goes through the safety layer first (the crisis protocol, saying it's an AI). Then the request is sorted
in code (companion/intents.py) and takes a fixed path: finding things moves the body; reminders are kept and
delivered in person; questions about the world use Muse Spark's web search; anything else is conversation, on
Glimmer unless it needs more thought. When the cloud is refused or unreachable, the device answers instead.

Pictures from the home go only to models on this computer (SAM 3.1 and Glimmer); Muse Spark gets words.
"""
import json
import re
import threading
import time
from dataclasses import dataclass, field

from openai import APIError

from .agent.assistant import MORNING, Assistant, needs_agent
from .agent.loop import plan_search
from .agent.tools import SearchTools, side
from .budget import Budget, BudgetExceeded
from .companion import answers
from .companion.attention import face_person
from .companion import pictures
from .companion.follow import follow
from .companion.intents import REFINE, parse
from .companion.reminders import Reminders, spoken_time
from .companion.safety import DISCLOSURE, Disclosure, respond
from .finder.search import Finder, Found, Segmenter
from .memory.glance import glance
from .memory.places import Places
from .models.common import Chat, Mask, Reply
from .models.retry import CloudUnavailable
from .router import Router
from .robot.body import Body
from .screen.state import ScreenState

GLANCE_EVERY_S = 5 * 60
HONEST = ("I can't do that from a chat. Say it to me directly, like: Andy, remind me in ten minutes to stretch, or: "
          "Andy, where are my keys?")
ANSWER_WITHIN_S = 60
REFINE_WITHIN_S = 10 * 60  # "make it sunset" changes the last picture, for ten minutes  # how long Andy's question ("remind you about what, and when?") waits for the answer
# A chat model claiming an action only the robot's own code takes (it set nothing; Andy's code would have said so).
CLAIMS = re.compile(r"\b(?:i'?ll|i will|i'?ve|i have|i'?m going to|got it[,.]? i'?ll)\s+(?:\w+\s+){0,2}?"
                    r"(?:remind|set (?:a|the|your)|keep an eye|watch|look for|find|found|search|point)\b", re.I)
HISTORY_TURNS, HISTORY_FORGET_S = 4, 30 * 60  # a conversation: its last few exchanges, forgotten after 30 quiet minutes
CLOUD_TROUBLE = (BudgetExceeded, CloudUnavailable, APIError, RuntimeError)  # RuntimeError: no key set


class NoCloud:
    """Stands in for Muse Spark when there's no key or the robot is offline: the router falls back to the device."""

    def chat(self, prompt: str, history=()) -> Reply:
        raise CloudUnavailable("no Model API key on this computer", [])


@dataclass
class Andy:
    body: Body
    segmenter: Segmenter
    device: Chat  # Muse Glimmer on this computer
    places: Places
    reminders: Reminders
    screen: ScreenState = field(default_factory=ScreenState)
    cloud: Chat | None = None  # Muse Spark for conversation
    spark: object | None = None  # the Model API client, for planning searches and web answers (words only)
    judge: object | None = None  # Glimmer's picture checks, on this computer
    glimmer: object | None = None  # the local llama-server client, for Glimmer planning searches itself
    home: str = ""  # where the person lives ("Miami, Florida"), for the weather and anything local; never guessed
    vision_where: str = "device"  # "cloud" only for a staged scene, where the finder uses SAM 3.1 through the API
    budget: Budget = field(default_factory=Budget)
    online: bool = True
    clock: object = time.time

    def __post_init__(self):
        self.finder = Finder(self.body, self.segmenter, check=self.judge.real if self.judge else None,
                             on_look=lambda yaw, pitch: self.screen.step(f"looking {side(yaw)}"))
        self.router = Router(self.device, self.cloud or NoCloud())
        self.disclosure = Disclosure(self.clock)
        self._last_glance = self.clock()
        self.screen.online = self.online
        self.refresh_panels()
        self._source = self._reason = ""
        self.lock = threading.RLock()  # one thing at a time moves the body: keyboard, voice or a reminder
        self.history: list[tuple[str, str]] = []  # this conversation, in memory only
        self._asked: tuple[str, float] | None = None  # a question Andy asked, waiting for its answer
        self.following = False
        self._drawing = None  # the last picture Muse Image made, to refine
        self._briefed = None  # the day of the last morning briefing
        self.assistant = Assistant(self)
        self.voice = None  # the voice server client (speed, loudness), when Andy speaks out loud
        self._last_said = ""  # for "say that again"
        self.quiet_until = 0.0  # "be quiet for an hour": no initiatives of Andy's own until then
        self.liveliness = 1.0  # "move less": how much body language
        self._stop_following = threading.Event()
        self.person: tuple[float, float] | None = None  # where the person is (yaw, pitch), to face them when talking
        self._pointed = False  # this turn pointed at something
        self.hold_point_s = 1.2 if hasattr(self.body, "motion") else 0.0  # the real robot holds a point a moment
        self._last_turn = float("-inf")

    # --- a turn ---

    def hear(self, text: str) -> str:
        with self.lock:
            self.screen.new_turn()
            if self.clock() - self._last_turn > HISTORY_FORGET_S:
                self.history = []  # a new conversation
            self._last_turn = self.clock()
            self.reminders.mention_missed(self.say)
            self._source = self._reason = ""
            self._pointed, self._said = False, []
            self.screen.doing("Thinking", "Looking at you")
            reply = respond(text, self._answer, self.disclosure, opening=self._say_now)
            rest = reply
            for part in self._said:  # what was already said as it came (the opening, streamed sentences)
                rest = rest.removeprefix(part).lstrip()
            if rest:
                self.face_person_to_speak()
                self.say(rest)
            self.refresh_panels()
            # The "I'm Andy, an AI robot." opening is the code's, not the model's: kept out so it isn't copied.
            self.history = (self.history + [(text, reply.removeprefix(DISCLOSURE).strip())])[-HISTORY_TURNS:]
            if parse(text).kind != "voice":
                self._last_said = reply.removeprefix(DISCLOSURE).strip()
            return reply

    def turn_to_person(self, yaw: float, pitch: float | None = None) -> None:
        """Turn towards the person without waiting: within the head's reach the body-language loop eases the head
        there; further round, the turn runs on its own thread. Either way the answer is being made meanwhile."""
        pitch = pitch if pitch is not None else (self.person[1] if self.person else -5.0)
        self.person = (yaw, pitch)
        face = getattr(self.body, "face", None)
        base = getattr(self.body, "_sent", (0.0, 0.0, 0.0))[2]
        if face and abs(yaw - base) <= getattr(self.body, "head_yaw", 30.0):
            face(yaw, pitch)
        elif face:
            threading.Thread(target=self.body.look, args=(yaw, pitch), kwargs={"precise": False}, daemon=True).start()
        else:
            self.body.look(yaw, pitch, precise=False)

    def face_person_to_speak(self) -> None:
        """Speak to the person, not to the thing: after pointing, hold it a moment, then turn to them."""
        if self.person is None:
            return
        yaw, pitch = self.person
        if abs(getattr(self.body, "yaw", yaw) - yaw) > 8 or abs(getattr(self.body, "pitch", pitch) - pitch) > 8:
            if self._pointed:
                time.sleep(self.hold_point_s)
            self.body.look(yaw, pitch, precise=False)
        face = getattr(self.body, "face", None)
        if face:
            face(yaw, pitch)  # and keep easing towards them while talking

    def say(self, text: str) -> None:
        self.screen.said(text, self._source, self._reason)
        before = (self.screen.state, self.screen.head)
        self.screen.doing("Speaking", before[1] if before[0] == "Pointing" else "Looking at you")
        try:
            self.body.say(text)
        finally:
            if before[0] in ("Working", "Pointing"):
                self.screen.doing(*before)
            else:
                self.screen.doing("Waiting")

    def use_staged_scene(self, api_segmenter) -> None:
        """Filming in a staged room: the finder's frames go to SAM 3.1 through the Model API, and the TV says so. The
        face tracker and the idle glance stay on this computer (and cost nothing)."""
        self.finder.segmenter, self.vision_where, self.screen.staged = api_segmenter, "cloud", True

    def set_online(self, online: bool) -> None:
        """The network came or went: the TV says so, and the cloud is only tried while it's there."""
        self.online = self.screen.online = online

    def refresh_panels(self) -> None:
        """The screen's side cards: the next reminder, and what Andy is keeping an eye on."""
        up = self.reminders.upcoming()
        if up:
            self.screen.reminder_next(up[0].text, up[0].at)
        else:
            self.screen.reminder_next(None)
        self.screen.keeping(self._memory(), self._memory_map())

    def _answer(self, text: str) -> str:
        i = parse(text, _now(self.clock))
        if self._asked and i.kind == "chat" and self.clock() - self._asked[1] <= ANSWER_WITHIN_S:
            i = parse(self._asked[0] + " " + text, _now(self.clock))  # the answer to Andy's question
        self._asked = None
        today = _now(self.clock).date()
        brief = bool(MORNING.search(text)) and self._briefed != today
        if brief or needs_agent(text):
            done = self.agent(text, brief)
            if done is not None:
                self._briefed = today if brief else self._briefed
                return done
        if i.kind == "voice":
            return self.adjust_voice(i.thing)
        if i.kind == "quiet":
            return self.be_quiet(i.at)
        if i.kind == "unquiet":
            self.quiet_until = 0.0
            self.screen.quiet("")
            self._set_liveliness(self.liveliness)
            return "Okay, I'm back to normal."
        if i.kind == "motion":
            return self.adjust_motion(i.thing)
        if i.kind == "find":
            return self.find(i.thing, text, i.hint)
        if i.kind == "follow":
            return self.follow(i.thing)
        if i.kind == "watch":
            self.places.watch(i.thing)
            return (f"I'll keep an eye on your {i.thing}. I only remember where I last saw {_it(i.thing)}, "
                    f"never a picture. Say 'forget my {i.thing}' to stop.")
        if i.kind == "forget":
            self.places.forget(i.thing)
            self.screen.remember_list(self._memory())
            return f"I've forgotten your {i.thing}."
        if i.kind == "remember":
            lines = self._memory()
            self.screen.remember_list(lines)
            return ("I'm keeping an eye on " + _join(self.places.watching()) + ". It's on the screen.") if lines \
                else "I'm not keeping an eye on anything. Say 'keep an eye on my keys' to start."
        if i.kind == "reminders":
            up = self.reminders.upcoming()[:5]
            if not up:
                return "You have no reminders."
            return "Your reminders: " + "; ".join(f"at {spoken_time(r.at)}, {r.text}" for r in up) + "."
        if i.kind == "remind":
            if not i.text:
                self._asked = ("remind me", self.clock())
                return "What should I remind you about, and when?"
            r = self.reminders.add(i.text, i.at, i.daily, now=self.clock())
            return f"I'll remind you {'every day ' if r.daily else ''}at {spoken_time(r.at)}: {r.text}."
        if i.kind == "describe":
            return self.describe(i.thing, holding="hold" in text.lower() or bool(re.search(r"\bthis\b", text, re.I)))
        if i.kind == "draw":
            return self.draw(i.text)
        if self._drawing and time.time() - self._drawing.made < REFINE_WITHIN_S and REFINE.search(text):
            return self.draw(text, refine=True)
        if i.kind == "help":
            self.screen.show_help()
            return ("I can find things and point at them, keep an eye on things, remind you, and look things up. "
                    "There are some ideas on the screen. Start with my name.")
        if i.kind == "world":
            return self.look_up(text)
        return self.talk(text)

    def _say_now(self, part: str) -> None:
        """Say part of this turn's reply as soon as it's ready (the hear() at the end says only the rest)."""
        self.face_person_to_speak()
        self.say(part.strip())
        self._said.append(part.strip())

    def talk(self, text: str) -> str:
        """Conversation, spoken sentence by sentence as the model writes it. Each sentence is checked first: one that
        claims an action the robot's own code didn't take stops the answer and is replaced with how to ask for it."""
        parts = []
        try:
            for sentence in self.router.stream(text, self.online, self.history):
                self._source, self._reason = self.router.last.where, self.router.last.reason  # known once it answers
                if CLAIMS.search(sentence):
                    self._reason += "; a promise the model can't keep was replaced"
                    parts.append(HONEST)
                    break
                parts.append(sentence)
                self._say_now(sentence)
        except APIError:
            parts.append("I'm having trouble thinking just now. Could you say that again in a minute?")
        if self._source:
            self.screen.used("Muse Spark" if self._source == "cloud" else "Muse Glimmer", self._source)
        return " ".join(parts)

    def look_up(self, question: str) -> str:
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "offline: no web search"
            return "I can't look things up right now, because I'm not connected."
        self.say("Let me look that up.")  # a web answer takes a few seconds
        self.screen.doing("Working", "Looking it up")
        try:
            ans = answers.ask(self.spark, question, budget=self.budget, home=self.home)
        except CLOUD_TROUBLE:
            self._source, self._reason = "device", "the web search didn't answer"
            return "I couldn't look that up just now. Please try again in a little while."
        self._source, self._reason = "cloud", "web search (Muse Spark)"
        self.screen.used("Muse Spark + web search", "cloud")
        self.screen.answered(ans.text, ans.sources, "cloud", self._reason)
        return ans.spoken

    def planners(self) -> list[tuple]:
        """Who can plan a search with the tools, best first: Muse Spark online, then Muse Glimmer on this computer."""
        out = []
        if self.online and self.spark is not None:
            out.append((self.spark, "muse-spark-1.3", True, "cloud", "search planned by Muse Spark; pictures checked here"))
        if self.glimmer is not None:
            out.append((self.glimmer, "muse-glimmer-30B", False, "device", "search planned by Muse Glimmer on this computer"))
        return out

    def gesture(self, name: str) -> None:
        g = getattr(self.body, "gesture", None)
        if g:
            g(name)

    def find(self, thing: str, request: str, hint: bool = False) -> str:
        """A plain "where are my keys" gets the fast fixed sweep; a request with a hint gets an agent that uses it."""
        self.screen.clear()
        self.screen.timer_start()
        checks = getattr(self.judge, "calls", 0)
        self.finder.looks = 0
        self.screen.looking(thing)
        self.say("Let me look.")  # answer at once: a search takes a few seconds
        self.screen.doing("Working", "Looking around the room")
        self.gesture("thinking")
        try:
            return self._find(thing, request, hint, checks)
        finally:
            self.gesture("idle")

    def _find(self, thing: str, request: str, hint: bool, checks: int) -> str:
        found, words = None, ""
        for client, model, paid, source, reason in (self.planners() if hint else []):
            tools = SearchTools(self.finder, self.places, self.judge, on_tool=self._tool_moves)
            on_look, self.finder.on_look = self.finder.on_look, None  # the plan's own steps show the progress
            try:
                plan = plan_search(client, request, tools, model=model, budget=self.budget, paid=paid)
            except CLOUD_TROUBLE as e:
                self.screen.step(f"{model} is unavailable ({type(e).__name__})")
                continue
            finally:
                self.finder.on_look = on_look
            for tool, _args, result in plan.steps:
                self.screen.step(f"{tool}: {result}")
            found, words = tools.pointed, ""  # found: Andy's words come from the tools, never the model's guesses
            self.screen.used(("Muse Spark" if paid else "Muse Glimmer") + " (plans)", source, plan.calls)
            self._source, self._reason = source, reason
            if found is None:
                self.screen.timer_stop()
                return plan.reply or self._not_found(thing)
            break
        if found is None:
            self._source, self._reason = "device", "fixed search on this computer"
            last = self.places.last_seen(thing)
            self.screen.step("recall: " + (f"last seen {side(last[0])}" if last else "no recent sighting"))
            self.gesture("searching")
            found = self.finder.find(thing, last)
            self.screen.step(f"looked {self.finder.looks} times" + (f"; {self.finder.why}" if self.finder.why else ""))
        self.screen.timer_stop()
        self.screen.used("SAM 3.1", self.vision_where, self.finder.looks)
        self.screen.used("Muse Glimmer (picture check)", "device", getattr(self.judge, "calls", 0) - checks)
        if found is None:
            return self._not_found(thing)
        self.places.saw(found.label, found.yaw, found.pitch, when=self.clock())
        self._pointed = True
        self.screen.doing("Pointing", f"At your {found.label}")
        self.gesture("found")
        words = words or self._found_words(found)
        self.screen.found(found, words)
        return words

    def adjust_voice(self, what: str) -> str:
        """"Say that again", "speak up", "speak more slowly": how Andy speaks, changed by voice and remembered."""
        if what == "repeat":
            return self._last_said or "I haven't said anything yet."
        v = self.voice
        if v is None:
            return "I can't change my voice here."
        steps = {"louder": ("loudness", 3.0, -12.0), "quieter": ("loudness", -3.0, -30.0),
                 "slower": ("speed", -0.1, 0.7), "faster": ("speed", 0.1, 1.3)}
        name, step, limit = steps[what]
        now = getattr(v, name)
        new = max(limit, now + step) if step < 0 else min(limit, now + step)
        if round(new, 2) == round(now, 2):
            return {"louder": "That's as loud as I go.", "quieter": "That's as quiet as I go.",
                    "slower": "That's as slowly as I speak.", "faster": "That's as fast as I speak."}[what]
        setattr(v, name, round(new, 2))
        self.save_voice()
        self.screen.notice(self.voice_levels())
        return "Is this better?"

    def voice_levels(self) -> str:
        """"Volume ●●●●○○○ · Speed ●●●○○○○": seven steps each, the middle one where Andy started."""
        v = self.voice
        loud = round((v.loudness + 30.0) / 3.0) + 1  # -30..-12 dBFS -> 1..7
        speed = round((v.speed - 0.7) / 0.1) + 1  # 0.7..1.3 -> 1..7
        bar = lambda n: "●" * n + "○" * (7 - n)  # noqa: E731
        return f"Volume {bar(loud)} · Speed {bar(speed)}"

    def be_quiet(self, seconds: float) -> str:
        """No initiatives of Andy's own (glances, looking for the person, turning to faces), calm and still, until
        then; it still answers when called, and reminds without searching the room."""
        self.quiet_until = self.clock() + seconds
        until = spoken_time(self.quiet_until)
        self.screen.quiet(f"Quiet until {until}")
        self._set_liveliness(0.3)
        return f"Okay, I'll keep quiet until {until}. I'll still answer if you call me."

    def quiet(self) -> bool:
        return self.clock() < self.quiet_until

    def adjust_motion(self, what: str) -> str:
        new = round(max(0.3, self.liveliness - 0.35) if what == "less" else min(1.0, self.liveliness + 0.35), 2)
        if new == self.liveliness:
            return "I'm as still as I go." if what == "less" else "That's as lively as I get."
        self.liveliness = new
        self._set_liveliness(new)
        self.save_voice()
        return "Like this?"

    def _set_liveliness(self, value: float) -> None:
        motion = getattr(self.body, "motion", None)
        if motion is not None:
            motion.liveliness = value

    def save_voice(self) -> None:
        path = self.places.path.parent / "voice.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = {"liveliness": self.liveliness}
        if self.voice is not None:
            saved.update(speed=self.voice.speed, loudness=self.voice.loudness)
        path.write_text(json.dumps(saved))

    def load_voice(self) -> None:
        path = self.places.path.parent / "voice.json"
        if path.exists():
            saved = json.loads(path.read_text())
            if self.voice is not None:
                self.voice.speed, self.voice.loudness = saved.get("speed", 1.0), saved.get("loudness", -21.0)
            self.liveliness = saved.get("liveliness", 1.0)
            self._set_liveliness(self.liveliness)

    def agent(self, request: str, brief: bool = False) -> str | None:
        """Several things at once, or the morning briefing: an agent plans over all of Andy's abilities. Muse Spark
        online, Muse Glimmer on this computer otherwise; None if neither can (the simple paths take over)."""
        brains = []
        if self.online and self.spark is not None:
            brains.append((self.spark, "muse-spark-1.3", True, "cloud"))
        if self.glimmer is not None:
            brains.append((self.glimmer, "muse-glimmer-30B", False, "device"))
        for client, model, paid, where in brains:
            try:
                turn = self.assistant.run(client, request, model, paid, self.budget, brief=brief)
            except CLOUD_TROUBLE:
                continue
            for tool, _args, result in turn.steps:
                self.screen.step(f"{tool}: {result}")
            name = "Muse Spark" if paid else "Muse Glimmer"
            self.screen.used(f"{name} (agent)", where, turn.calls)
            self._source = where
            self._reason = f"{name} planned it with Andy's abilities ({len(turn.steps)} steps)"
            return turn.reply or "Done."
        return None

    def follow(self, thing: str, seconds: float = 30.0) -> str:
        """Find the thing, then follow it with the eyes as it's moved, until "stop" (said any time) or 30 s."""
        self.finder.last_found = None
        self.find(thing, f"where is the {thing}")
        found = self.finder.last_found
        if found is None:
            return self._not_found(thing)
        self._stop_following.clear()
        self.following = True
        self.say(f"Following your {thing}. Say stop when you're done.")
        self.screen.doing("Following", f"Your {thing}")
        frames = [0]

        def seen(frame, mask, yaw, pitch):
            frames[0] += 1
            self.screen.found(Found(thing, yaw, pitch, mask.score or 0.5, frame, mask, frames[0]),
                              f"Following your {thing}")

        try:
            why = follow(self.body, self.finder.segmenter, thing, (found.yaw, found.pitch), seen,
                         self._stop_following.is_set, seconds)
        finally:
            self.following = False
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", self.vision_where, frames[0])
        return {"stopped": "Okay, I've stopped.", "time": f"That's enough following for now. Your {thing} is "
                f"{side(self.body.yaw)}.", "lost": f"I lost sight of your {thing}."}[why]

    def draw(self, what: str, refine: bool = False) -> str:
        """A picture from the person's words, with Muse Image (words only leave the house); shown and saved."""
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "pictures need the Model API"
            return "I can only make pictures when I'm connected."
        self.say("Let me draw that. It takes a little while." if not refine else "Let me change it.")
        self.screen.doing("Working", "Drawing")
        try:
            drawing = pictures.draw(self.spark, what, self._drawing if refine else None, budget=self.budget)
        except (*CLOUD_TROUBLE, pictures.NoPicture):
            self._source, self._reason = "device", "the picture didn't come back"
            return "I couldn't make that picture just now. Please try again in a little while."
        finally:
            self.screen.doing("Waiting")
        self._drawing = drawing
        path = pictures.save(drawing)
        self._source, self._reason = "cloud", "a picture from your words (Muse Image)"
        self.screen.used("Muse Image", "cloud")
        self.screen.drawn(drawing.image, drawing.prompt, f"Saved in Pictures, Andy, as {path.name}")
        return ("Here it is, on the screen. I've changed it." if refine else "Here's your picture, on the screen.") + \
            " I've saved it in your Pictures folder. You can ask me to change it."

    def describe(self, place: str = "", holding: bool = False) -> str:
        """"What am I holding?", "what's on the table?": look, then Glimmer says what it sees, on this computer."""
        judge = getattr(self.judge, "describe", None)
        if judge is None:
            return "I can't describe things right now."
        self.say("Let me see.")
        self.screen.doing("Working", "Looking")
        box, where = None, f"on the {place}" if place else ""
        try:
            self.gesture("searching")
            if holding:  # face the person, then look a little lower, at their hands
                yaw, pitch = self.person or (getattr(self.body, "yaw", 0.0), 0.0)
                self.body.look(yaw, min(pitch + 18.0, 30.0))
                frame = self.body.capture()
                hands = [m for m in self.segmenter.find(frame, "hand") if m.score is None or m.score >= 0.4]
                if hands:  # around both hands: what's held is between them
                    box = (min(m.box[0] for m in hands), min(m.box[1] for m in hands),
                           max(m.box[2] for m in hands), max(m.box[3] for m in hands))
                where = "in the person's hands"
            else:
                if place:  # tables and the floor are below eye level
                    self.body.look(getattr(self.body, "yaw", 0.0), 28.0)
                frame = self.body.capture()
            seen = judge(frame, where, box)
        finally:
            self.gesture("idle")
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", "device", 1 if holding else 0)
        self.screen.used("Muse Glimmer (looks)", "device")
        self._source, self._reason = "device", "Glimmer looked, on this computer"
        if box and frame.image:
            self.screen.found(Found("what you're holding", self.body.yaw, self.body.pitch, 1.0, frame,
                                    Mask("what you're holding", box, None, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))),
                              seen or "")
        return seen or "I couldn't get a good look. Could you hold it a little closer to me?"

    def stop_following(self) -> None:
        self._stop_following.set()

    def _tool_moves(self, starting: bool) -> None:
        """Still while a tool looks; thinking while the model decides what to do next."""
        self.gesture("searching" if starting else "thinking")

    def _found_words(self, f: Found) -> str:
        where = side(f.yaw)
        if not f.reachable:
            return f"I can't turn far enough to point, but your {f.label} is {where}."
        return f"I see your {f.label}, {where}." + (" Right where I last saw it." if f.remembered else "")

    def _not_found(self, thing: str) -> str:
        if "picture" in self.finder.why:
            return f"I only saw a picture of {thing} on a screen. Could you tell me where you last had {_it(thing)}?"
        return f"I couldn't find your {thing}. Could you tell me where you last had {_it(thing)}?"

    def _memory(self) -> list[str]:
        lines = []
        for label in self.places.watching():
            last, at = self.places.last_seen(label, now=self.clock()), self.places.seen_at(label)
            lines.append(f"{label}: " + (f"seen {_ago(self.clock() - at)}, {side(last[0])}" if last else "not seen yet"))
        return lines

    def _memory_map(self) -> list[dict]:
        """For the TV's map: where each watched thing was last seen, and how long ago (none: not seen yet)."""
        out = []
        for label in self.places.watching():
            last, at = self.places.last_seen(label, now=self.clock()), self.places.seen_at(label)
            out.append({"label": label, "yaw": last[0], "pitch": last[1], "ago_s": round(self.clock() - at)}
                       if last else {"label": label})
        return out

    # --- between turns ---

    def tick(self) -> None:
        """Deliver reminders that are due, and glance around now and then for watched things."""
        with self.lock:
            self._tick()

    def _tick(self) -> None:
        now = self.clock()
        if self.quiet_until and not self.quiet():  # quiet time is over
            self.quiet_until = 0.0
            self.screen.quiet("")
            self._set_liveliness(self.liveliness)
        for r in self.reminders.due(now):  # asked for, so said even in quiet time; but without searching the room
            self.reminders.deliver(r, (lambda: True) if self.quiet() else self._find_person, self.say, now)
        if not self.quiet() and self.places.watching() and now - self._last_glance >= GLANCE_EVERY_S:
            self._last_glance = now
            self.gesture("searching")
            self.screen.doing("Working", "Glancing around the room")
            try:
                glance(self.body, self.segmenter, self.places)
            finally:
                self.gesture("idle")
                self.screen.doing("Waiting")
        self.refresh_panels()

    def _find_person(self):
        self.gesture("searching")
        try:
            direction = face_person(self.body, self.segmenter)
        finally:
            self.gesture("idle")
        if direction:
            self.person = direction
        return direction


def _now(clock):
    import datetime as dt

    return dt.datetime.fromtimestamp(clock())


def _join(items: list[str]) -> str:
    items = [f"your {x}" for x in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' * (minutes != 1)} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' * (hours != 1)} ago"


def _it(thing: str) -> str:
    return "them" if thing.endswith("s") and not thing.endswith("ss") else "it"
