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
from .companion import cupgame, pictures, web
from .companion.language import LANGUAGES, TVWords, asked_for
from .companion.follow import follow
from .companion.intents import REFINE, WEB_CLOSE, WEB_MORE, parse
from .companion.reminders import Reminders, spoken_time
from .companion.safety import CRISIS_REPLY, DISCLOSURE, Disclosure, crisis, respond
from .finder.geometry import LITE, pixel_to_angles
from .finder.search import Finder, Found, Segmenter
from .memory.glance import glance
from .memory.mine import Mine
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
WEB_MORE_WITHIN_S = 3 * 60  # "scroll down", "go back": the web page on the TV, for three minutes
REFINE_WITHIN_S = 10 * 60  # "make it sunset" changes the last picture, for ten minutes  # how long Andy's question ("remind you about what, and when?") waits for the answer
# A chat model claiming an action only the robot's own code takes (it set nothing; Andy's code would have said so).
CLAIMS = re.compile(r"\b(?:i'?ll|i will|i'?ve|i have|i'?m going to|got it[,.]? i'?ll)\s+(?:\w+\s+){0,2}?"
                    r"(?:remind|set (?:a|the|your)|keep an eye|watch|look for|find|found|search|point)\b", re.I)
AGAIN = re.compile(r"^\W*(?:yes|yeah|yep|sure|ok(?:ay)?|again|one more|let'?s go|go on|why not)"
                   r"(?:\W+(?:please|again|one more|let'?s go|let'?s play|why not|sure|yes|go))*\W*$", re.I)  # not "okay thanks"
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
        self.mine = Mine(self.places.path.parent / "mine.json")  # things Andy knows by sight, as numbers
        self._alike: float | None = None  # how like the person's own the last checked thing was
        self._not_yours = False  # this find saw one, but someone else's
        self.finder = Finder(self.body, self.segmenter, check=self._check,
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
        self.playing = False  # the cup game: "done" ends the shuffle
        self.cup_score = [0, 0]  # Andy, the person: this session's cup games, in memory only
        self._again_until = 0.0  # Andy just asked "again?" after a cup game
        self._offered: tuple | None = None  # (thing, when, yaw, pitch): Andy offered to keep an eye on it
        self.language = "en"  # "es": Andy hears and speaks Spanish (companion/language.py)
        self.translator = None  # Muse Glimmer on this computer, translating; set where Glimmer runs
        self._browser = None  # a clean browser on this computer, made when first asked to use the web
        self._web: tuple[str, str, float] | None = None  # (the request, the last run's response id, when)
        self._drawing = None  # the last picture Muse Image made, to refine
        self._briefed = None  # the day of the last morning briefing
        self.assistant = Assistant(self)
        self.voice = None  # the voice server client (speed, loudness), when Andy speaks out loud
        self._last_said = ""  # for "say that again"
        self.quiet_until = 0.0  # "be quiet for an hour": no initiatives of Andy's own until then
        self.liveliness = 1.0  # "move less": how much body language
        self.describe_in_background = hasattr(self.body, "motion")  # on the robot, never make a turn wait for it
        self._stop_following = threading.Event()
        self.person: tuple[float, float] | None = None  # where the person is (yaw, pitch), to face them when talking
        self._pointed = False  # this turn pointed at something
        self.hold_point_s = 1.2 if hasattr(self.body, "motion") else 0.0  # the real robot holds a point a moment
        self._last_turn = float("-inf")

    # --- a turn ---

    @property
    def asr_language(self) -> str:
        return LANGUAGES[self.language].asr

    def hear(self, text: str) -> str:
        with self.lock:
            if self.language != "en" and self.translator is not None and not crisis(text):
                text = self.translator.to_english(text, self.language)  # the rules and tools work in English
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
            if reply != CRISIS_REPLY:  # crisis words never go to a model, not even as history
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
        if self.language != "en" and self.translator is not None:
            text = self.translator.spoken(text, self.language, DISCLOSURE, CRISIS_REPLY)
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
        offered, self._offered = self._offered, None
        if offered and self.clock() - offered[1] <= ANSWER_WITHIN_S:
            thing, _, yaw, pitch = offered
            yes = AGAIN.match(text) or re.match(r"^\W*(?:yes\W+)?(?:please do|go ahead|do that|that would be (?:great|nice)|"
                                                r"keep an eye on (?:it|them)(?: please)?)\W*$", text, re.I)
            if yes:
                self.places.watch(thing)
                self.places.saw(thing, yaw, pitch, when=self.clock())  # where it was just found: the first place
                self.refresh_panels()
                return f"I'll keep an eye on your {thing}. I only remember where I last saw {_it(thing)}, never a picture."
            no = re.match(r"^\W*(?:no thanks?(?: you)?|not now|nope|that'?s ok(?:ay)?|no)\b[\s,.!]*", text, re.I)
            if no and not text[no.end():].strip():
                return "Okay. Just ask me whenever you need it."
            if no:  # "No, where are my keys?": the rest is a request of its own
                text = text[no.end():]
        i = parse(text, _now(self.clock))
        if self._asked and i.kind == "chat" and self.clock() - self._asked[1] <= ANSWER_WITHIN_S:
            i = parse(self._asked[0] + " " + text, _now(self.clock))  # the answer to Andy's question
        self._asked = None
        today = _now(self.clock).date()
        brief = bool(MORNING.search(text)) and self._briefed != today
        if (to := asked_for(text)) is not None:
            return self.set_language(to)
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
        if i.kind == "last_seen":
            return self.last_seen(i.thing, text)
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
            by_sight = self.mine.forget(i.thing)
            self.screen.remember_list(self._memory())
            return f"I've forgotten your {i.thing}" + (", and what it looks like." if by_sight else ".")
        if i.kind == "mine":
            return self.learn_mine(i.thing)
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
        if self._web and self.clock() - self._web[2] <= WEB_MORE_WITHIN_S and i.kind == "chat":
            if WEB_CLOSE.search(text):
                self._web = None
                self.screen.clear()
                return "Okay, I've closed it."
            if WEB_MORE.search(text):
                return self.use_the_web(text, more=True)
        if i.kind == "pointing":
            return self.pointed_at()
        if i.kind == "going_out":
            return self.going_out()
        if i.kind == "things_map":
            return self.draw_my_things()
        if i.kind == "web":
            return self.use_the_web(text)
        again, self._again_until = self.clock() <= self._again_until and AGAIN.match(text), 0.0
        if i.kind == "game" or (again and i.kind == "chat"):
            return self.cup_game()
        if i.kind == "describe":
            return self.describe(i.thing, holding="hold" in text.lower() or bool(re.search(r"\bthis\b", text, re.I)))
        if i.kind == "draw":
            return self.draw(i.text)
        if self._drawing and time.time() - self._drawing.made < REFINE_WITHIN_S and REFINE.search(text):
            return self.draw(text, refine=True)
        if i.kind == "help":
            self.screen.show_help()
            return ("I can find things and point at them, keep an eye on things, remind you, look things up, and play "
                    "the cup game. "
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
                if self._source != self.router.last.where and self.router.last.where == "cloud":
                    self.screen.sent("Muse Spark", text, len(self.history))
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
            self.screen.sent("Muse Spark + web search", question + (f" (home: {self.home})" if self.home else ""))
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
        self.finder.looks, self._alike, self._not_yours = 0, None, False
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
                if paid:
                    self.screen.sent("Muse Spark (plans the search)", request)
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
        self._note_place(found.label, found.frame, found.mask)
        self._pointed = True
        self.screen.doing("Pointing", f"At your {found.label}")
        self.gesture("found")
        words = words or self._found_words(found)
        self.screen.found(found, words)
        return words + self._offer_to_watch(found.label, (found.yaw, found.pitch))

    def _offer_to_watch(self, thing: str, where=(0.0, 0.0), times: int = 3, within_s: float = 7 * 24 * 3600) -> str:
        """Asked for the same thing a few times this week, and not kept an eye on: offer, once a week. Only the word and
        when it was asked are kept, on this computer."""
        path = self.places.path.parent / "asked.json"
        try:
            asked = json.loads(path.read_text()) if path.exists() else {}
        except ValueError:
            asked = {}
        now = self.clock()
        entry = asked.setdefault(thing, {"at": [], "offered": 0.0})
        entry["at"] = [t for t in entry["at"] if now - t <= within_s] + [now]
        offer = (len(entry["at"]) >= times and thing not in self.places.watching()
                 and now - entry["offered"] > within_s)
        if offer:
            entry["offered"] = now
            self._offered = (thing, now, *where)  # a yes or no answers it
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asked))
        if not offer:
            return ""
        return (f" You've asked me about your {thing} {len(entry['at'])} times this week. Shall I keep an eye on "
                f"{_it(thing)}?")

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

    def _tv_language(self) -> None:
        """The TV follows: its labels (page.html) and Andy's own words on it (translated in the background)."""
        self.screen.language = "Español · en esta computadora" if self.language == "es" else ""
        self.screen.lang = self.language
        if self.language != "en" and self.translator is not None and getattr(self.screen.words, "language", "") != self.language:
            self.screen.words = TVWords(self.translator, self.language)

    def set_language(self, to: str) -> str:
        """"Andy, habla español" / "speak English": hearing, voice and captions switch, and it's remembered."""
        if to != "en" and self.translator is None:
            return "I can only speak English on this computer for now."
        if self.voice is not None:
            self._own_voice  # noqa: B018 - the voice it was started with, remembered before the first switch
        if to == self.language:
            return "Okay." if to == "en" else "I'm already speaking Spanish."
        self.language = to
        if self.voice is not None:
            self.voice.voice = LANGUAGES[to].voice if to != "en" else self._own_voice
        self.screen.notice("Español" if to == "es" else "English")
        self._tv_language()
        self.save_voice()
        self._source, self._reason = "device", "hearing and speaking switched, on this computer"
        return "Okay, I'll speak Spanish now." if to == "es" else "Okay, I'll speak English now."

    def save_voice(self) -> None:
        path = self.places.path.parent / "voice.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = {"liveliness": self.liveliness, "language": self.language}
        if self.voice is not None:
            saved.update(speed=self.voice.speed, loudness=self.voice.loudness)
        path.write_text(json.dumps(saved))

    @property
    def _own_voice(self) -> str:
        """The voice Andy was started with (--voice-name), for English."""
        if not hasattr(self, "_started_voice"):
            self._started_voice = getattr(self.voice, "voice", LANGUAGES["en"].voice)
        return self._started_voice

    def load_voice(self) -> None:
        path = self.places.path.parent / "voice.json"
        if self.voice is not None:
            self._own_voice  # noqa: B018 - remembered before anything changes it
        if path.exists():
            saved = json.loads(path.read_text())
            if self.voice is not None:
                self.voice.speed, self.voice.loudness = saved.get("speed", 1.0), saved.get("loudness", -21.0)
            self.liveliness = saved.get("liveliness", 1.0)
            self._set_liveliness(self.liveliness)
            if saved.get("language", "en") in LANGUAGES and (saved.get("language") == "en" or self.translator):
                self.language = saved.get("language", "en")
                self._tv_language()
                if self.voice is not None and self.language != "en":
                    self.voice.voice = LANGUAGES[self.language].voice

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
                if paid:
                    self.screen.sent("Muse Spark (agent)", request)
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

    def cup_game(self) -> str:
        """The cup game (companion/cupgame.py): watch the ball go under a cup, record the shuffle, replay it with SAM 3.1
        Object Multiplex on this computer, and point at the cup. Then watch the reveal, and keep score."""
        track = getattr(self.segmenter, "track", None)
        if track is None:
            return "I can't play the cup game right now: it needs my eyes on this computer."
        self._stop_following.clear()
        self.following = self.playing = True  # the face tracker leaves the head alone until the reveal is over
        try:
            return self._cup_game(track)
        finally:
            self.following = self.playing = False
            self.screen.doing("Waiting")
            self.gesture("idle")

    def _cup_game(self, track) -> str:
        self.screen.clear()
        yaw = self.person[0] if self.person else getattr(self.body, "yaw", 0.0)
        self.body.look(yaw, 25.0)  # the table between us
        self.gesture("searching")  # a still head: the clip needs it
        self.screen.doing("Playing", "Watching the table")
        self.say("Let's play! Show me the ball, then hide it under a cup and shuffle, not too fast. Say done when "
                 "you're finished.")
        try:
            r = cupgame.play(self.body, self.segmenter, track, self._stop_following.is_set, self._game_stage)
        except RuntimeError:  # the local SAM 3.1 or the camera didn't answer
            r = cupgame.Result("broken")
        self.playing = False  # the shuffle is over: "done" means nothing now
        if r.frames:
            self.screen.used("SAM 3.1 Object Multiplex", "device", r.frames)
            self._source = "device"
            self._reason = f"SAM 3.1 followed every cup through {r.frames} frames, on this computer ({r.seconds:.0f} s)"
        if r.how != "found":
            self.screen.game({"lost": "I lost track", "stopped": "Another time"}.get(r.how, "Let's try again"))
            if r.how in ("lost", "no_cups", "no_ball", "not_hidden"):
                self._again_until = self.clock() + ANSWER_WITHIN_S  # "yes" starts another round
            return {"lost": "I lost track of the cups, sorry. Shall we go again, a little slower?",
                    "no_cups": "I need to see two or three cups on the table in front of me. Shall we try again?",
                    "no_ball": "I didn't see the ball. Show it to me first, then hide it under a cup.",
                    "not_hidden": "I can still see the ball. Hide it under a cup, and we'll play again.",
                    "stopped": "Okay, another time.",
                    "broken": "Sorry, my eyes aren't working properly just now."}[r.how]
        self.body.point(r.yaw, r.pitch)
        self.gesture("found")
        cups = [t for t in r.tracks if len(t.path) >= r.frames / 2 or t is r.chosen]  # not a moment's misdetection
        trails = [([(x, y) for _, x, y in t.path[::max(1, len(t.path) // 40)]], t is r.chosen) for t in cups]
        found = Found("cup", r.yaw, r.pitch, r.chosen.end.score or 0.5, r.frame, r.chosen.end, r.frames)
        self.screen.found(found, "It's under this one", trails)
        self.say("It's under this one! Lift it up.")
        won = self._reveal(r)
        self._again_until = self.clock() + ANSWER_WITHIN_S  # "yes" or "again" starts another round
        if won is None:
            return "Shall we play again?"
        self.cup_score[0 if won else 1] += 1
        andy, you = self.cup_score
        self.screen.score = f"Andy {andy} · You {you}"
        self.screen.found(found, ("I got it! " if won else "You got me! ") + self.screen.score, trails)
        if won:
            self.gesture("found")
        score = f"That's {andy} to {you}" + (" to me." if andy > you else " to you." if you > andy else ".")
        return ("Yes! I kept my eye on it. " if won else "Oh, you got me! Well played. ") + score + " Again?"

    def _game_stage(self, what: str, **info) -> None:
        if what == "ball":
            self.screen.game("Show me the ball", "Then hide it under a cup and shuffle.")
        elif what == "seen":
            self.gesture("found")  # the antennas only: the head stays still for the clip
            self.screen.game("I see the ball", "Now hide it under a cup and shuffle.")
        elif what == "shuffling":
            self.screen.game("Watching the cups", "Shuffle them, then stop, or say done.")
        elif what == "replaying":
            self.gesture("thinking")
            self.screen.game("Replaying the shuffle", f"SAM 3.1 is following every cup through {info['frames']} "
                                                      "frames, on this computer.")
            self.say("Let me replay that.")

    def _reveal(self, r, seconds: float = 8.0) -> bool | None:
        """After "lift it up": was the ball under the cup Andy pointed at? None if it wasn't seen in time."""
        cam = LITE.scaled(r.frame.width, r.frame.height)
        cups = {t.id: pixel_to_angles(*t.end.center, r.frame.yaw, r.frame.pitch, cam) for t in r.tracks if t.end}
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                frame = self.body.capture()
                balls = [m for m in self.segmenter.find(frame, "ball") if m.score is None or m.score >= 0.4]
            except RuntimeError:  # the camera or SAM 3.1 didn't answer: no verdict, but the game ends properly
                return None
            if balls:
                at = pixel_to_angles(*max(balls, key=lambda m: m.score or 0.5).center, frame.yaw, frame.pitch,
                                     LITE.scaled(frame.width, frame.height))
                return min(cups, key=lambda c: (cups[c][0] - at[0]) ** 2 + (cups[c][1] - at[1]) ** 2) == r.chosen.id
        return None

    def learn_mine(self, thing: str, views: int = 4) -> str:
        """"This is my mug": look at it in the person's hands, a few times as they turn it, and keep what it looks like
        as numbers (DINOv2, on this computer; memory/mine.py). Later finds skip a mug that isn't theirs."""
        embed = getattr(self.segmenter, "embed", None)
        if embed is None:
            return "I can't learn things by sight right now."
        self.say(f"Hold your {thing} up so I can see it, and turn it slowly.")
        self.screen.clear()
        self.screen.doing("Working", f"Learning your {thing}")
        yaw, pitch = self.person or (getattr(self.body, "yaw", 0.0), 0.0)
        vectors, shown = [], None
        self.gesture("searching")
        try:
            self.body.look(yaw, min(pitch + 12.0, 30.0))  # a little lower than the face: the hands
            for _ in range(views):
                frame = self.body.capture()
                masks = self.finder._masks(frame, thing, self.segmenter)  # local, even when filming a staged scene
                if masks:
                    held = max(masks, key=lambda m: (m.box[2] - m.box[0]) * (m.box[3] - m.box[1]))  # nearest: largest
                    vectors += embed(frame, [held])
                    shown = shown or (frame, held)
        except RuntimeError:  # the local models didn't answer
            vectors = []
        finally:
            self.gesture("idle")
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", "device", views)
        if len(vectors) < 2:
            return f"I couldn't see your {thing} clearly. Could you hold it a little closer to me, and ask again?"
        self.mine.learn(thing, vectors, now=self.clock())
        self.screen.used("DINOv2 (knows it by sight)", "device", len(vectors))
        self._source, self._reason = "device", "learned by sight on this computer, kept as numbers, not a picture"
        frame, held = shown
        self.screen.found(Found(thing, frame.yaw, frame.pitch, held.score or 0.5, frame, held, views),
                          f"Your {thing}: I'll know it by sight")
        return (f"Got it. I'll know your {thing} from now on. I keep what it looks like as numbers on this computer, "
                f"never a picture. Say forget my {thing} to remove it.")

    def _check(self, frame, mask) -> bool:
        """The finder's second opinion on what it found: a real thing (not a picture of one, Glimmer), and when the
        person has shown Andy theirs, theirs (as alike as the views Andy kept)."""
        if self.judge and not self.judge.real(frame, mask):
            return False
        embed = getattr(self.segmenter, "embed", None)
        if not self.mine.knows(mask.label) or embed is None:
            return True
        try:
            alike = self.mine.how_alike(mask.label, embed(frame, [mask])[0])
        except RuntimeError:
            return True  # can't tell: SAM 3.1 and Glimmer already agreed it's a real one
        self.screen.used("DINOv2 (knows it by sight)", "device")
        self.screen.step(f"a {mask.label}, {alike:.0%} like yours: " + ("yours" if alike >= self.mine.alike else "not yours"))
        self._alike = alike
        if alike < self.mine.alike:
            self.finder.rejected, self._not_yours = f"a {mask.label}, but not yours", True
            return False
        return True

    def use_the_web(self, request: str, more: bool = False) -> str:
        """"Show me a banana bread recipe on the TV" (companion/web.py): Muse Spark's web search picks the page, a
        clean browser on this computer opens it, and Muse Spark's computer use brings what was asked into view. The TV
        shows every step. Screenshots of web pages go to the cloud; the camera never does."""
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "the web needs the Model API"
            return "I can only use the web when I'm connected."
        if self._browser is None:
            try:
                import playwright  # noqa: F401 - the optional 'browse' extra
            except ImportError:
                return "I can't use the web on this computer yet."
            self._browser = web.Browser()
        first = self._web[0] if more and self._web else \
            re.sub(r"\s*\bon (?:the|my|your) (?:tv|telly|screen|television)\b", "", request, flags=re.I).strip(" ,.!?")
        self.say("Okay." if more else "Let me find that for you.")
        self.screen.doing("Working", "On the web")
        shots = [0]  # screenshots of web pages sent, counted as they go: the receipt says so even if the run fails

        def step(jpeg, words, point):
            self.screen.web(jpeg, first, words, point, url=self._browser.url())

        try:
            if more:
                previous = self._web[1]  # None after a run that stopped early: its last step was never answered
                task = request if previous else f"{request} (The browser shows the page for: {first}.)"
                self.screen.sent("Muse Spark (uses the web)", request)
                run = web.use_the_web(self.spark, self._browser, task, step, previous=previous, budget=self.budget,
                                      max_steps=2, within_s=40.0, shots=shots)
            else:
                self.screen.sent("Muse Spark (web search)", request + (f" (home: {self.home})" if self.home else ""))
                url = web.best_page(self.spark, request, self.home, budget=self.budget)
                self._browser.open(url) if url else self._browser.search(request)
                self.screen.used("Muse Spark (web search)", "cloud")
                run = web.use_the_web(self.spark, self._browser, web.SHOW.format(task=request, url=url or "search results"),
                                      step, budget=self.budget, max_steps=3, within_s=45.0, shots=shots)
            self.screen.web(self._browser.screenshot(), first, "", None, url=self._browser.url())
        except (*CLOUD_TROUBLE, TimeoutError) as e:
            if isinstance(e, web.BrowserTrouble):  # a fresh browser next time
                self._browser.close()
                self._browser = None
            self._source, self._reason = "device", f"the web didn't answer ({type(e).__name__})"
            return "I couldn't get that page just now. Please try again in a little while."
        finally:
            self.screen.doing("Waiting")
            if shots[0]:
                self.screen.sent("Muse Spark (computer use)", f"{shots[0]} screenshots of the web page")
                self.screen.used("Muse Spark (computer use)", "cloud", shots[0])
        self._web = (first, None if run.stopped else run.response_id, self.clock())
        self._source, self._reason = "cloud", "Muse Spark used the web: screenshots of web pages, never the camera"
        if "sign-in" in run.stopped:
            return "That page wants a sign-in or a payment, so I've stopped there. I'll leave that part to you."
        if run.stopped:  # out of steps or time: say so plainly rather than the model's half-finished narration
            return "That's as far as I could get. What I found is on the TV."
        return (run.answer or "It's on the TV.") + ("" if more else " You can say scroll down, or go back.")

    def pointed_at(self) -> str:
        """"What's that?" while pointing: Glimmer, on this computer, says what the person points at and on which side;
        SAM 3.1 finds it, in the same picture if it's in view, else Andy turns that way and looks; then it points at it
        too, and asks if that's the one (joint attention: both looking at the same thing)."""
        ask = getattr(self.judge, "pointing", None)
        if ask is None:
            return "I can't tell where you're pointing right now. Could you tell me what it is?"
        self.screen.clear()
        self.finder.looks = 0
        self.say("Let me see where you're pointing.")
        self.screen.doing("Working", "Looking where you point")
        self.gesture("searching")
        try:
            yaw, pitch = self.person or (getattr(self.body, "yaw", 0.0), 0.0)
            self.body.look(yaw, min(pitch + 8.0, 25.0))  # the person and what's around them
            frame = self.body.capture()
            seen = ask(frame)
            self.screen.used("Muse Glimmer (looks)", "device")
            if seen is None:
                self._source, self._reason = "device", "Glimmer looked, on this computer"
                return "I can't tell what you're pointing at. Could you tell me what it is?"
            thing, where = seen
            self.screen.step(f"pointing at: {thing}, {where}")
            masks = self.finder._masks(frame, thing, self.segmenter)
            want = {"left": 0.25, "right": 0.75}.get(where.split()[-1] if where else "", 0.5) * frame.width
            found = None
            if masks and "edge" not in where:  # in view: the one on the side the person points to
                m = min(masks, key=lambda m: abs(m.center[0] - want))
                cam = LITE.scaled(frame.width, frame.height)
                found = self.finder.confirm(thing, *pixel_to_angles(*m.center, frame.yaw, frame.pitch, cam))
            if found is None:  # out of view: turn that way first, then the rest of the room
                views = self.finder.views
                first = [v for v in views if (v[0] > yaw) == ("left" in where)] if where != "middle" else []
                self.finder.views = tuple(first + [v for v in views if v not in first])
                try:
                    found = self.finder.find(thing)
                finally:
                    self.finder.views = views
            else:
                self.finder.point(found)
        finally:
            self.gesture("idle")
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", "device", 1)  # the first picture: always the local SAM
        self.screen.used("SAM 3.1", self.vision_where, self.finder.looks)
        self._source, self._reason = "device", "Glimmer saw where you pointed; SAM 3.1 found it"
        if found is None:
            return f"I think you're pointing at the {thing}, but I can't find it from here. Could you show me?"
        self._pointed = True
        self.gesture("found")
        words = f"You mean the {thing}? It's {side(found.yaw)}."
        self.screen.found(found, words)
        return words

    def going_out(self) -> str:
        """"I'm going out": look again where each watched thing was last seen, and point at any still here (it isn't
        with the person); meanwhile, on its own thread, Muse Spark looks up the weather. Then the next reminder."""
        self.screen.clear()
        weather: dict = {}
        asking = None
        if self.online and self.spark is not None:
            question = ("Going out now: will I need an umbrella, a jacket or sun protection? Answer in at most 12 words, "
                        "without the source.")
            self.screen.sent("Muse Spark + web search", question + (f" (home: {self.home})" if self.home else ""))

            def ask():
                try:
                    text = answers.ask(self.spark, question, budget=self.budget, home=self.home).text.strip()
                    weather["text"] = text + ("" if text.endswith((".", "!", "?")) else ".")
                except CLOUD_TROUBLE:
                    pass

            asking = threading.Thread(target=ask, daemon=True)
            asking.start()  # the cloud works while the robot looks
        watched = self.places.watching()
        self.finder.looks = 0
        if watched:
            self.say("Let me check you have everything.")
        items, here = [], []
        self.gesture("searching")
        self.screen.doing("Working", "Checking your things")
        try:
            for label in watched:
                last = self.places.last_seen(label, now=self.clock())
                found = self.finder.confirm(label, *last) if last else None
                if found:
                    self.finder.point(found)
                    self.places.saw(label, found.yaw, found.pitch, when=self.clock())
                    near = (self.places.history(label) or [{}])[-1].get("near") or side(found.yaw)
                    self.say(f"Your {label} {'are' if _it(label) == 'them' else 'is'} still here, {near}.")
                    here.append(label)
                    items.append({"thing": label, "here": True, "words": f"Still here, {near}"})
                else:
                    items.append({"thing": label, "here": None if not last else False,
                                  "words": "Not seen lately" if not last else "Not where I last saw it: with you?"})
                self.screen.going_out(items)
        finally:
            self.gesture("idle")
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", self.vision_where, self.finder.looks)
        up = [r for r in self.reminders.upcoming() if r.at - self.clock() <= 6 * 3600][:1]
        next_up = f"at {spoken_time(up[0].at)}, {up[0].text}" if up else ""
        if asking:
            asking.join(timeout=20.0)
            if weather.get("text"):
                self.screen.used("Muse Spark + web search", "cloud")
        self.screen.going_out(items, weather.get("text", ""), next_up)
        self._source = "device" if not weather.get("text") else "cloud"
        self._reason = "looked again where your things were last seen; the weather from the web" if weather.get("text") \
            else "looked again where your things were last seen, on this computer"
        words = []
        if not watched:
            words.append("Have you got your keys, your wallet and your phone? If you say 'keep an eye on my keys', I'll "
                         "check for you next time.")
        else:
            away = [i["thing"] for i in items if i["here"] is False]
            if here:
                words.append(f"Don't forget {_join(here)}.")
            if away:
                them = _it(away[0]) if len(away) == 1 else "them"
                words.append(f"I didn't see {_join(away)} where I last saw {them}, so I hope "
                             f"{'it’s' if them == 'it' else 'they’re'} with you.")
        if next_up:
            words.append(f"Remember: {next_up}.")
        if weather.get("text"):
            words.append(weather["text"])
        return " ".join(words + ["Have a lovely time!"])

    def draw_my_things(self) -> str:
        """"Draw me a map of my things": Muse Image paints where the watched things were last seen, from words only
        (what each is near, and which way from the robot). A drawing from memory, not a picture of the room."""
        places = []
        for label in self.places.watching():
            last = self.places.last_seen(label, now=self.clock())
            if last:
                history = self.places.history(label)
                places.append((label, (history[-1]["near"] or "") if history else "", side(last[0])))
        if not places:
            return "I haven't seen any of your things yet. Say 'keep an eye on my keys' to start."
        if not self.online or self.spark is None:
            return "I can only make pictures when I'm connected. " + " ".join(f"Your {t}: {s}." for t, _, s in places)
        prompt = pictures.things_map(places)
        self.say("Let me draw where your things are. It takes a little while.")
        self.screen.doing("Working", "Drawing")
        try:
            self.screen.sent("Muse Image", pictures.things_words(places))  # the receipt: the words about the home
            drawing = pictures.draw(self.spark, prompt, budget=self.budget)
        except (*CLOUD_TROUBLE, pictures.NoPicture):
            self._source, self._reason = "device", "the picture didn't come back"
            return "I couldn't make that picture just now. Please try again in a little while."
        finally:
            self.screen.doing("Waiting")
        self._drawing = drawing
        path = pictures.save(drawing)
        self._source, self._reason = "cloud", "a map from what Andy remembers, in words (Muse Image)"
        self.screen.used("Muse Image", "cloud")
        self.screen.drawn(drawing.image, "where your things are",
                          f"A drawing from what I remember, not a photo. Saved in Pictures, Andy, as {path.name}")
        return "Here's where your things are, on the screen. It's a drawing from what I remember, not a photo."

    def draw(self, what: str, refine: bool = False) -> str:
        """A picture from the person's words, with Muse Image (words only leave the house); shown and saved."""
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "pictures need the Model API"
            return "I can only make pictures when I'm connected."
        self.say("Let me draw that. It takes a little while." if not refine else "Let me change it.")
        self.screen.doing("Working", "Drawing")
        try:
            self.screen.sent("Muse Image", what)
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
        yours = ", the one you showed me" if self._alike is not None and self.mine.knows(f.label) else ""
        return f"I see your {f.label}{yours}, {where}." + (" Right where I last saw it." if f.remembered else "")

    def _not_found(self, thing: str) -> str:
        if self._not_yours or "not yours" in self.finder.why:
            return f"I saw a {thing}, but not yours. Could you tell me where you last had {_it(thing)}?"
        if "picture" in self.finder.why:
            return f"I only saw a picture of {thing} on a screen. Could you tell me where you last had {_it(thing)}?"
        return f"I couldn't find your {thing}. Could you tell me where you last had {_it(thing)}?"

    def _memory(self) -> list[str]:
        lines = []
        for label in self.places.watching():
            last, at = self.places.last_seen(label, now=self.clock()), self.places.seen_at(label)
            if not last:
                lines.append(f"{label}: not seen yet")
                continue
            history = self.places.history(label)
            where = (history[-1]["near"] if history and history[-1]["near"] else side(last[0]))
            moved = f" (moved at {spoken_time(history[-1]['since'])})" if len(history) > 1 else ""
            lines.append(f"{label}: seen {_ago(self.clock() - at)}, {where}{moved}")
        watched = self.places.watching()
        lines += [f"{k}: I know it by sight" for k in self.mine.known() if k not in watched]
        return lines

    def _note_place(self, label: str, frame, mask) -> None:
        """A new place for a watched thing: Glimmer says, in a few words, what it's near. Only the words are kept;
        the frame goes as soon as they're written."""
        history = self.places.history(label)
        where_near = getattr(self.judge, "where_near", None)
        if not where_near or not history or history[-1]["near"]:
            return  # nothing to describe with, not watched, or this place already has its words

        def describe():
            words = where_near(frame, mask)
            if words:
                self.places.near(label, words)
                self.refresh_panels()

        if self.describe_in_background:
            threading.Thread(target=describe, daemon=True).start()
        else:
            describe()

    def last_seen(self, thing: str, request: str) -> str:
        """"When did you last see my keys?": from memory, without moving. Not watched: look for it instead."""
        history = self.places.history(thing)
        if not history:
            if thing in self.places.watching():
                return f"I haven't seen your {thing} since you asked me to keep an eye on {_it(thing)}."
            return self.find(thing, request)
        now, last = self.clock(), history[-1]
        where = last["near"] or side(last["yaw"])
        words = f"I last saw your {thing} {_ago(now - last['at'])}, {where}."
        if len(history) > 1:
            before = history[-2]
            words += (f" Before that, {before['near'] or side(before['yaw'])}, until {spoken_time(before['at'])}.")
        self.screen.remember_list(self._memory())
        return words

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
                glance(self.body, self.segmenter, self.places, on_seen=self._note_place)
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
