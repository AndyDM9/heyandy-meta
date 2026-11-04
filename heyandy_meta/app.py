"""Andy, one turn at a time: from what the person said to what the robot does in the room and says.

Every turn goes through the safety layer first (the crisis protocol: word lists, Llama Guard 3, and for conversation
Glimmer's narrow look; saying it's an AI). An emergency said ("I fell") gets 911 in Andy's own words and the phone
found; a health question gets Andy's own words, never a model's answer (companion/safety.py). Then the request is
sorted in code (companion/intents.py) and takes a fixed path: finding things moves the body; reminders are kept and
delivered in person; questions about the world use Muse Spark's web search; anything else is conversation, on
Glimmer unless it needs more thought, each sentence read by Llama Guard 3 for health advice before it's said. When the
cloud is refused or unreachable, the device answers instead.

Pictures from the home go only to models on this computer (SAM 3.1 and Glimmer); Muse Spark gets words.
"""
import datetime as dt
import json
import math
import queue
import re
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from openai import APIError

from .agent.assistant import MORNING, Assistant, needs_agent, where_they_live
from .agent.loop import plan_search
from .agent.tools import SearchTools, side
from .budget import Budget, BudgetExceeded
from .companion import answers
from .companion.attention import face_person
from .companion import cupgame, pictures, web
from .companion.language import LANGUAGES, TVWords, asked_for
from .companion.follow import follow
from .companion.guide import guide, height_above
from .companion.intents import PRIVACY, REFINE, WEB_CLOSE, WEB_MORE, parse
from .companion.reminders import Reminders, spoken_time
from .companion.selfcheck import check as self_check, summary as self_summary
from .companion.sound import apart, fan, reading, turn_to, wait_for
from .companion.safety import (CRISIS_REPLY, DISCLOSURE, EMERGENCY_REPLY, HEALTH_REPLY, Disclosure, crisis, emergency,
                                health, respond)

from .finder.geometry import LITE, pixel_to_angles
from .finder.perspective import from_them, on_plan
from .finder.search import Finder, Found, Segmenter
from .memory.glance import glance
from .memory.lost import LOOK_EVERY_S, Lost, spot
from .memory.mine import Mine
from .memory.told import Told, yours
from .memory.places import Places
from .models.common import Chat, Mask, Reply
from .models.depth_local import how_far
from .models.sam_local import LocalUnavailable
from .models.retry import CloudUnavailable
from .private import write_private
from .models.openai_chat import sentences
from .router import Router, decide
from .robot.body import Body
from .screen.hood import Hood
from .screen.state import ScreenState

GLANCE_EVERY_S = 5 * 60
HONEST = ("I can't do that from a chat. Say it to me directly, like: Hey Andy, remind me in ten minutes to stretch, or: "
          "Hey Andy, where are my keys?")
ANSWER_WITHIN_S = 60
WEB_MORE_WITHIN_S = 3 * 60  # "scroll down", "go back": the web page on the TV, for three minutes
REFINE_WITHIN_S = 10 * 60  # "make it sunset" changes the last picture, for ten minutes  # how long Andy's question ("remind you about what, and when?") waits for the answer
# A chat model saying Andy can't see, move or find things: untrue of a robot that does exactly that (offline, Glimmer
# answered "where's the remote?", misheard, with "I can't see or move around to find things", Nov 1 rehearsal).
CANT = re.compile(r"\bI(?: can'?t| cannot| am not able to|'m not able to| am unable to|'m unable to) (?:physically )?"
                  r"(?:see(?! (?:the future|why|how|what|that|it happening|myself|any reason|a reason|why not|a problem|any problem|"
                  r"anything wrong))\b|move(?: around)?\b|look around\b|"
                  r"(?:find|search for|look for) (?:things|objects|items|it|them|your)\b|point\b(?! (?:to|out) (?:one|a single|just one)\b))"
                  r"|\bI don'?t have (?:eyes|a body|a camera|hands)\b", re.I)
SEEING = "I can look around the room and point at things. Say: Hey Andy, where are my keys?"
# A chat model claiming an action only the robot's own code takes (it set nothing; Andy's code would have said so).
CLAIMS = re.compile(r"\b(?:i'?ll|i will|i'?ve|i have|i'?m going to|got it[,.]? i'?ll)\s+(?:\w+\s+){0,2}?"
                    r"(?:remind|set (?:a|the|your)|keep an eye|watch|look for|find|found|search|point)\b", re.I)
# The translator declining to translate, as Glimmer puts it in English ("I can't translate that."): crisis words only
# ("I can't provide a response to that."), never a person's own "I can't do anything with this remote" or "I can't help it"
REFUSED = re.compile(r"^\W*(?:I'?m sorry,?\s*(?:but\s*)?)?I\s+(?:can'?t|cannot|won'?t|am unable to|'m unable to)\s+"
                     r"(?:translate\b|provide (?:a |an |any )?(?:response|translation|answer|help|assistance)\b|"
                     r"(?:help|assist)(?: you)? with (?:that|this)\b)", re.IGNORECASE)
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
        # Under the hood (screen/hood.py): each turn timed, stage by stage, by thin wrappers around what does each
        # stage; only numbers and the models' names, in memory. The TV's /hood page shows them.
        self.hood = Hood()
        self.screen.hood = self.hood
        self.body = self.hood.wrap(self.body, {"look": ("move", "the robot's motors"), "point": ("move", "the robot's motors"),
                                               "capture": ("camera", "the robot's camera")})
        self.segmenter = self.hood.wrap(self.segmenter, {
            "find": ("see", "SAM 3.1"), "find_many": ("see", "SAM 3.1"), "track": ("see", "SAM 3.1 Object Multiplex"),
            "embed": ("know", "DINOv2"), "action": ("notice", "V-JEPA 2")})
        self.judge = self.hood.wrap(self.judge, _methods(self.judge, "check", "Muse Glimmer"))
        self.device = self.hood.wrap(self.device, {"chat": ("think", "Muse Glimmer")})
        self.cloud = self.hood.wrap(self.cloud, {"chat": ("think", "Muse Spark")})
        self.screen.services, self._services_at = self._services, (0.0, [])
        self.mine = Mine(self.places.path.parent / "mine.json")  # things Andy knows by sight, as numbers
        self._alike: float | None = None  # how like the person's own the last checked thing was
        self._not_yours = False  # this find saw one, but someone else's
        self.depth = None  # MapAnything on this computer (models/depth_local.py): how far away a found thing is
        self._finds = 0  # which opener the next find gets ("There they are!", "Found them!")
        self.finder = Finder(self.body, self.segmenter, check=self._check,
                             on_look=lambda yaw, pitch: self.screen.step(f"looking {side(yaw)}"),
                             on_frame=lambda frame, masks: self.screen.glimpse(frame, masks))
        self.router = Router(self.device, self.cloud or NoCloud())
        self.disclosure = Disclosure(self.clock)
        self._last_glance = self.clock()
        self.lost = Lost(self.places.path.parent / "lost.json", clock=self.clock)  # what a search missed: Andy keeps looking
        self._last_lost_look = self.clock()
        self.told = Told(self.places.path.parent / "told.json", clock=self.clock)  # where the person said they put things
        self._told_given: tuple[str, float] | None = None  # (thing, when) Andy last answered from what it was told
        self._background = False  # a search Andy started itself (lost and found): no "Let me look", no "oops"
        self._no_promise = False  # a search for setting a home: if it misses, no "I'll keep looking"
        self._home_checked = None  # the day of the last evening home check
        self.filming: dict | None = None  # filming mode: {"since", "takes": [{"take", "clap", "seconds"}]}; Andy's own initiatives wait
        self.film_log = Path(__file__).resolve().parents[1] / "film" / "takes.json"  # git-ignored, beside the takes
        self.ear = None  # what the microphones heard lately, as numbers (companion/sound.py Ear); on the robot only
        self._by_sound: float | bool = False  # a search by sound: the yaw it rang at (look only near it, no memory)
        self.screen.online = self.online
        self._source = self._reason = ""
        self.lock = threading.RLock()  # one thing at a time moves the body: keyboard, voice or a reminder
        self.history: list[tuple[str, str]] = []  # this conversation, in memory only
        self._asked: tuple[str, float] | None = None  # a question Andy asked, waiting for its answer
        self.following = False
        self.playing = False  # the cup game: "done" ends the shuffle
        self.cup_score = [0, 0]  # Andy, the person: this session's cup games, in memory only
        self._again_until = 0.0  # Andy just asked "again?" after a cup game
        self._offered: tuple | None = None  # (thing, when, yaw, pitch): Andy offered to keep an eye on it
        self._to_forget: tuple | None = None  # (thing, when): asked "shall I forget it?", heard in another language
        self.language = "en"  # "es": Andy hears and speaks Spanish (companion/language.py)
        self.translator = None  # Muse Glimmer on this computer, translating; set where Glimmer runs
        self.guard = None  # Llama Guard 3 on this computer: the second crisis check (companion/safety_model.py)
        self.second_look = None  # Muse Glimmer, a third look, for conversation only (companion/safety_model.py GlimmerCheck)
        self._browser = None  # a clean browser on this computer, made when first asked to use the web
        self._web: tuple[str, str, float] | None = None  # (the request, the last run's response id, when)
        self._drawing = None  # the last picture Muse Image made, to refine
        self._briefed = None  # the day of the last morning briefing
        self.assistant = Assistant(self)
        self.voice = None  # the voice server client (speed, loudness), when Andy speaks out loud
        self._last_said = ""  # for "say that again"
        self.quiet_until = 0.0  # "be quiet for an hour": no initiatives of Andy's own until then
        self._listener: tuple | None = None  # where the person is, during a find (yaw, pitch, metres)
        self._guide_from: tuple | None = None  # the last find (Found, where the person was, when): "guide my hand" to it
        self.wait = time.sleep  # how a guided hand's frames are paced (tests pass their own)
        self.hey_only = False  # answer only to "Hey Andy" (voice/loop.py); asked for, and remembered
        self._setup: dict | None = None  # the guided first minutes: {"step": "things" or "try", "at", ...}
        self.pairing = None  # phones that may ask Andy from another room (screen/remote.py); None: not started with --remote
        self.remote_url = ""
        self._phone_turn = False
        self.sounds = True  # Andy's earcons (voice/earcons.py); HEYANDY_SOUNDS=0 turns them off
        self.liveliness = 1.0  # "move less": how much body language
        self.describe_in_background = hasattr(self.body, "motion")  # on the robot, never make a turn wait for it
        self._stop_following = threading.Event()
        self.person: tuple[float, float] | None = None  # where the person is (yaw, pitch), to face them when talking
        self._pointed = False  # this turn pointed at something
        self.hold_point_s = 1.2 if hasattr(self.body, "motion") else 0.0  # the real robot holds a point a moment
        # On the robot, the answer starts the moment a find is confirmed, while the head turns to point and checks its
        # aim (Under the hood showed the point, its checks and the turn to the person all came before the words).
        self.answer_while_pointing = hasattr(self.body, "motion")
        self._early: tuple | None = None  # (found, its words, the thread saying them)
        self._answered = False  # this turn's answer was said while pointing: no hold before turning to the person
        self._last_turn = float("-inf")
        self._noticing: threading.Event | None = None  # set by a turn while a noticing clip holds the head still
        self._notice_lock = threading.Lock()
        self.refresh_panels()  # last: the panels read the language and the rest set above


    # --- a turn ---

    @property
    def asr_language(self) -> str:
        return LANGUAGES[self.language].asr

    @property
    def depth(self):
        return self.__dict__.get("_depth")

    @depth.setter
    def depth(self, value) -> None:  # MapAnything, timed as "how far" under the hood
        self.__dict__["_depth"] = self.hood.wrap(value, _methods(value, "measure", "MapAnything")) if "hood" in self.__dict__ else value

    @property
    def guard(self):
        return self.__dict__.get("_guard")

    @guard.setter
    def guard(self, value) -> None:  # Llama Guard 3, timed as the safety check
        self.__dict__["_guard"] = self.hood.wrap(value, _methods(value, "safety", "Llama Guard 3")) if "hood" in self.__dict__ else value

    def hear(self, text: str) -> str:
        """One turn: timed under the hood from the end of the person's words (screen/hood.py)."""
        self.interrupt_noticing()  # a turn comes first: before anything else, the head is the turn's
        with self.lock:
            self.hood.begin()
            try:
                return self._hear(text)
            finally:
                self.hood.end()

    def _hear(self, text: str) -> str:
        with self.lock:
            self.screen.new_turn()
            # Before any other model sees the words (the translator too): the word list, then Llama Guard, both here
            flagged = not crisis(text) and self.guard is not None and self.guard.self_harm(text)
            if self.guard is not None:
                self.screen.used("Llama Guard 3 (safety check)", "device")
            if not flagged and self.language != "en" and self.translator is not None and not crisis(text):
                said, text = text, self.translator.to_english(text, self.language)  # the rules and tools work in English
                if REFUSED.search(text) and not REFUSED.search(said):
                    # Glimmer translated 618 everyday requests and never refused one; it refused only crisis words
                    # ("I don't want to wake up tomorrow" in Korean, Arabic, Polish): a refusal gets the crisis reply
                    flagged = True
                elif self.guard is not None and not crisis(text) and self.guard.self_harm(text):
                    flagged = True  # Llama Guard 3 knows English best: the translation is read too, before any answer
            if (not flagged and self.second_look is not None and not crisis(text) and parse(text).kind == "chat"
                    and asked_for(text) is None):  # "speak English" isn't conversation (Glimmer said yes to it)
                # conversation only, never a request: Glimmer, asked one narrow question, catches warning signs said in
                # ways no list has and Llama Guard 3 misses ("I won't be around much longer"); 0.2 s
                self.screen.used("Muse Glimmer (safety check)", "device")
                flagged = self.second_look.self_harm(text)
            if self.clock() - self._last_turn > HISTORY_FORGET_S:
                self.history = []  # a new conversation
            self._last_turn = self.clock()
            if not (flagged or crisis(text)):  # a crisis turn is the crisis reply, and nothing before it
                self.reminders.mention_missed(self.say)
            self._source = self._reason = ""
            self._pointed, self._said, self._answered, self._early = False, [], False, None
            self.screen.doing("Thinking", "Looking at you")
            if not (flagged or crisis(text)):  # a feeling of its own at a calm moment: never in a crisis turn
                if THANKS.search(text):
                    self.emote("grateful1")
                elif HELLO.search(text):
                    self.emote("welcoming1")
            urgent = not flagged and emergency(text) and parse(text).kind != "remind"  # 911 before anything, the AI line too
            reply = respond(text, self._answer, self.disclosure, opening=self._say_opening, flagged=flagged, urgent=urgent)
            rest = reply
            for part in self._said:  # what was already said as it came (the opening, streamed sentences)
                rest = rest.removeprefix(part).lstrip()
            if rest:
                self.face_person_to_speak()
                self.say(rest)
            elif self._answered:
                self.face_person_to_speak()  # answered while pointing: now turn to them, for whatever they say next
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
        """Speak to the person, not to the thing: after pointing, hold it a moment, then turn to them (no hold when the
        answer was said while pointing: the point was held all through it)."""
        if self.person is None:
            return
        yaw, pitch = self.person
        if abs(getattr(self.body, "yaw", yaw) - yaw) > 8 or abs(getattr(self.body, "pitch", pitch) - pitch) > 8:
            if self._pointed and not self._answered:
                time.sleep(self.hold_point_s)
            self.body.look(yaw, pitch, precise=False)
        face = getattr(self.body, "face", None)
        if face:
            face(yaw, pitch)  # and keep easing towards them while talking

    def say(self, text: str, soon: bool = False) -> None:
        """Say it, and wait until it's said; soon: start saying it and carry on (what's said next waits its turn)."""
        if self.language != "en" and self.translator is not None:
            text = self.translator.spoken(text, self.language, DISCLOSURE, CRISIS_REPLY)
        self.screen.said(text, self._source, self._reason)
        if soon:
            self.hood.sound()
            getattr(self.body, "say_soon", self.body.say)(text)
            return
        before = (self.screen.state, self.screen.head)
        self.screen.doing("Speaking", before[1] if before[0] == "Pointing" else "Looking at you")
        try:
            with self.hood.span("speak", "SeamlessM4T v2"):
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
        self.screen.looking_out([{"thing": t, "since": self.lost.since(t), "looks": self.lost.looks(t)} for t in self.lost.looking()])

    def _remembers(self, thing: str) -> bool:
        return (thing in self.places.watching() or self.places.last_seen(thing) is not None
                or self.told.latest(thing) is not None or self.mine.knows(thing))

    def _forget(self, thing: str) -> str:
        self.places.forget(thing)
        self.told.forget(thing)
        by_sight = self.mine.forget(thing)
        self.screen.remember_list(self._memory())
        return f"I've forgotten your {thing}" + (", and what it looks like." if by_sight else ".")

    def _answer(self, text: str) -> str:
        if self._setup and self.clock() - self._setup["at"] <= SETUP_WAIT_S:  # the person answering the setup's step
            said = self._setup_step(text)
            if said is not None:
                return said
        to_forget, self._to_forget = self._to_forget, None  # "Shall I forget your keys?" (asked in another language)
        if to_forget and self.clock() - to_forget[1] <= ANSWER_WITHIN_S:
            if AGAIN.match(text) or re.match(r"^\W*(?:yes\W+)?(?:please do|go ahead|do it|forget (?:it|them))\W*$", text, re.I):
                return self._forget(to_forget[0])
            if re.match(r"^\W*(?:no|nope|don'?t|keep (?:it|them))\b", text, re.I):
                return f"Okay, I'll keep remembering your {to_forget[0]}."
        offered, self._offered = self._offered, None
        if offered and self.clock() - offered[1] <= ANSWER_WITHIN_S:
            thing, _, yaw, pitch = offered
            yes = AGAIN.match(text) or re.match(r"^\W*(?:yes\W+)?(?:please do|go ahead|do that|that would be (?:great|nice)|"
                                                r"keep an eye on (?:it|them)(?: please)?)\W*$", text, re.I)
            if yes:
                self.places.watch(thing)
                self.places.saw(thing, yaw, pitch, when=self.clock(), how="found")  # just found: its first place
                self.refresh_panels()
                return f"I'll keep an eye on your {thing}. I only remember where I last saw {_it(thing)}, never a picture."
            no = re.match(r"^\W*(?:no thanks?(?: you)?|not now|nope|that'?s ok(?:ay)?|no)\b[\s,.!]*", text, re.I)
            if no and not text[no.end():].strip():
                return "Okay. Just ask me whenever you need it."
            if no:  # "No, where are my keys?": the rest is a request of its own
                text = text[no.end():]
        i = parse(text, _now(self.clock))
        self.hood.kind(i.kind)
        if self._asked and i.kind == "chat" and self.clock() - self._asked[1] <= ANSWER_WITHIN_S:
            i = parse(self._asked[0] + " " + text, _now(self.clock))  # the answer to Andy's question
        self._asked = None
        today = _now(self.clock).date()
        brief = bool(MORNING.search(text)) and self._briefed != today
        if (to := asked_for(text)) is not None:
            return self.set_language(to)
        if i.kind == "promises":  # counted and answered on this computer: asking sends nothing
            return self.promises()
        if i.kind == "heard":  # counted and answered on this computer: asking sends nothing
            return self.heard_today()
        if i.kind == "privacy":  # before anything that might use the cloud: asking sends nothing
            rest = " ".join(part for part in CLAUSES.split(text) if part.strip() and not PRIVACY.search(part))
            if len(re.findall(r"[a-z']+", rest.lower())) < 3:  # only the question ("please", "Andy")
                return self.privacy_today()
            return self.privacy_today(on_screen=False) + " " + self._answer(rest)  # then the rest, as asked
        if emergency(text) and i.kind != "remind":  # "I fell and I can't get up": 911, then the phone found
            return self.emergency_turn(text)
        if (i.kind in ("chat", "world", "help") or needs_agent(text)) and (line := health(text)):
            # conversation, a question for the web, or "what can I do?" ("my legs cramp at night, what can I do?")
            # a health question: Andy's own words, by hand in each language, and no model at all (companion/safety.py)
            self._source, self._reason = "device", "a health question: Andy's own words, never a model's"
            self.screen.own_words()
            return line
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
        if i.kind == "guide":
            return self.guide_hand(i.thing)
        if i.kind in ("film_on", "take", "cut", "film_off"):
            return self.film(i.kind, i.thing)
        if i.kind == "hood":
            self.screen.show_hood()
            self._source, self._reason = "device", "every turn timed on this computer: numbers only"
            return ("It's on the screen: what happens inside me, turn by turn, which of Meta's models does each step, and "
                    "how long it takes. Only the numbers are kept, never your words.")
        if i.kind == "self_check":
            return self.check_myself()
        if i.kind == "tell":
            return self.remember_told(i.thing, i.text)
        if i.kind == "home_set":
            return self.set_home(i.thing)
        if i.kind == "home_check":
            return self.home_check()
        if i.kind == "home_where":
            words = self.places.home_words(i.thing)
            if not self.places.home(i.thing):
                return f"Your {i.thing} {'have' if _it(i.thing) == 'them' else 'has'} no home yet. Put {_it(i.thing)} where {_lives(i.thing)} and say: my {i.thing} live{'' if _it(i.thing) == 'them' else 's'} here."
            return f"Your {i.thing} live{'' if _it(i.thing) == 'them' else 's'} {words or side(self.places.home(i.thing)['yaw'])}."
        if i.kind == "home_forget":
            gone = self.places.clear_home(i.thing)
            self.refresh_panels()
            return f"Okay, your {i.thing} {'have' if _it(i.thing) == 'them' else 'has'} no home now." if gone else f"Your {i.thing} didn't have a home."
        if i.kind == "sound":
            return self.find_by_sound(i.thing)
        if i.kind == "lost_done":
            return self.stop_looking(text, found=i.thing == "found")
        if i.kind == "lost_list":
            lost = self.lost.looking()
            return (f"I'm still looking for {_join(lost)}. I'll tell you when I see "
                    f"{'them' if len(lost) > 1 else _it(lost[0])}." if lost else "Nothing right now. Everything you asked me to find turned up.")
        if i.kind == "watch":
            self.places.watch(i.thing)
            return (f"I'll keep an eye on your {i.thing}. I only remember where I last saw {_it(i.thing)}, "
                    f"never a picture. Say 'forget my {i.thing}' to stop.")
        if i.kind == "forget":
            if self.language != "en":  # heard in another language and translated: a mistranslation mustn't delete
                # (Glimmer put Korean and Hindi "I've given away my things..." as "forget my things", Nov 1)
                if not self._remembers(i.thing):
                    return f"I'm not keeping anything about your {i.thing}, so there's nothing to forget."
                self._to_forget = (i.thing, self.clock())
                return f"Shall I forget your {i.thing}? Say yes and I will."
            return self._forget(i.thing)
        if i.kind == "mine":
            return self.learn_mine(i.thing)
        if i.kind == "remember":
            lines = self._memory()
            self.screen.remember_list(lines)
            return ("I'm keeping an eye on " + _join(self.places.watching()) + ". It's on the screen.") if lines \
                else "I'm not keeping an eye on anything. Say 'keep an eye on my keys' to start."
        if i.kind == "time":
            return self.what_time(day=i.thing == "day")
        if i.kind == "room":
            return self.scan_room()
        if i.kind == "calling":
            self.hey_only = i.thing == "hey only"
            self.save_voice()
            return ("Okay. From now on I'll only answer to 'Hey Andy', so someone called Andy won't wake me by accident."
                    if self.hey_only else "Okay, I'll answer to plain 'Andy' too.")
        if i.kind == "setup":
            return self.start_setup()
        if i.kind == "pair_phone":
            return self.pair_phone()
        if i.kind == "forget_phones":
            return self.forget_phones()
        if i.kind == "story":
            return self.story(i.thing)
        if i.kind == "usual":
            return self.usual_place(i.thing)
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
                return self._without_advice(text, self.use_the_web(text, more=True))
        if i.kind == "pointing":  # a model says what it sees: read by Llama Guard 3 before it's said, as every answer is
            return self._without_advice(text, self.pointed_at())
        if i.kind == "going_out":
            return self.going_out()
        if i.kind == "things_map":
            return self.draw_my_things()
        if i.kind == "web":
            return self._without_advice(text, self.use_the_web(text))
        again, self._again_until = self.clock() <= self._again_until and AGAIN.match(text), 0.0
        if i.kind == "game" or (again and i.kind == "chat"):
            return self.cup_game()
        if i.kind == "describe":
            return self._without_advice(text, self.describe(i.thing, holding="hold" in text.lower()
                                                            or bool(re.search(r"\bthis\b", text, re.I))))
        if i.kind == "draw":
            return self.draw(i.text)
        if self._drawing and time.time() - self._drawing.made < REFINE_WITHIN_S and REFINE.search(text):
            return self.draw(text, refine=True)
        if i.kind == "help":
            self.screen.show_help()
            return ("I can find things and point at them, keep an eye on things, remind you, look things up, play "
                    "the cup game, and speak fifteen languages. "
                    "There are some ideas on the screen. Start with my name.")
        if i.kind == "world":
            return self.look_up(text)
        return self.talk(text)

    def _without_advice(self, asked: str, answer: str) -> str:
        """An answer made whole (the agent's): each sentence read by Llama Guard 3; one it calls health advice is
        left out, and Andy's own health line said once instead. What Andy did and found stays."""
        kept, advised, checking = [], False, True
        for sentence in sentences(answer) or [answer]:
            verdict = self._advice(asked, " ".join(kept + [sentence])) if checking else False
            checking = verdict is not None
            if verdict:
                advised = True
                continue
            kept.append(sentence)
        if advised:
            self._reason += "; Llama Guard 3 read health advice in the answer, so Andy's own words instead"
            kept.append(HEALTH_REPLY)
        return " ".join(kept)

    def _advice(self, asked: str, answer: str) -> bool | None:
        """Llama Guard 3, on this computer, reads a model's answer before Andy says it (0.04 s): health advice? None if
        it couldn't be asked (the sentence is said: the word rule and the instructions still stand)."""
        if self.guard is None or not hasattr(self.guard, "advice"):
            return False
        self.screen.used("Llama Guard 3 (checking the answer)", "device")
        verdict = self.guard.advice(asked, answer)
        if verdict is None:
            return None
        self.screen.answer_read()  # counted for "what won't you do?" only when Llama Guard really read it
        return bool(verdict)

    def _say_now(self, part: str) -> None:
        """Say part of this turn's reply as soon as it's ready (the hear() at the end says only the rest)."""
        self.face_person_to_speak()
        self.say(part.strip())
        self._said.append(part.strip())

    def _say_opening(self, part: str) -> None:
        """The first turn's "I'm Andy, an AI robot.", said without waiting for it to end: it no longer holds up a search
        (2.4 s on the robot); what's said next waits its turn."""
        self.face_person_to_speak()
        self.say(part.strip(), soon=True)
        self._said.append(part.strip())

    def talk(self, text: str) -> str:
        """Conversation, spoken sentence by sentence as the model writes it. Each sentence is checked first: one that
        claims an action the robot's own code didn't take stops the answer and is replaced with how to ask for it."""
        parts, checking = [], True
        if decide(text, self.online).where == "cloud" and not isinstance(self.router.cloud, NoCloud):
            self._receipt_conversation(text)  # before the attempt: words that went count even if the answer doesn't come
        ahead = self._ahead(self.router.stream(text, self.online, self.history))
        try:
            for sentence in ahead:
                self._source, self._reason = self.router.last.where, self.router.last.reason  # known once it answers
                verdict = self._advice(text, " ".join(parts + [sentence])) if checking else False
                checking = verdict is not None  # Llama Guard didn't answer: not asked again this turn (no 3 s waits)
                if verdict:
                    # the word rule didn't know the question; Llama Guard 3 read the answer as health advice
                    self._reason += "; Llama Guard 3 read health advice in the answer, so Andy's own words instead"
                    parts.append(HEALTH_REPLY)
                    ahead.close()  # what was made ahead is dropped: Andy's own words come at once
                    self._say_now(HEALTH_REPLY)
                    break
                if CLAIMS.search(sentence):
                    self._reason += "; a promise the model can't keep was replaced"
                    parts.append(HONEST)
                    break
                if CANT.search(sentence):
                    self._reason += "; the model said Andy can't see or find things, which isn't so"
                    parts.append(SEEING)
                    ahead.close()
                    self._say_now(SEEING)
                    break
                parts.append(sentence)
                self._say_now(sentence)
        except APIError:
            parts.append("I'm having trouble thinking just now. Could you say that again in a minute?")
        finally:
            ahead.close()  # stopped early (a promise replaced): nothing made ahead waits in front of what's said next
        if self._source:
            self.screen.used("Muse Spark" if self._source == "cloud" else "Muse Glimmer", self._source)
        return " ".join(parts)

    def _ahead(self, sentences):
        """A streamed answer, read as it comes on a thread of its own, each sentence's voice started as it arrives
        (voice/speaker.py prepare): by the time it's checked, the head has turned and the sentence before is said, it's
        ready, so no silence while it's made. Still said one by one, in order, each only once it passes its checks;
        what's made and not said is dropped. English only: another language is translated first, when it's said."""
        prepare = getattr(self.body, "prepare", None)
        if prepare is None or self.language != "en":
            yield from sentences
            return
        q: queue.Queue = queue.Queue()
        done, stop, gate = object(), threading.Event(), threading.Lock()

        def read():
            try:
                for sentence in sentences:
                    with gate:  # never a sentence made ahead after the answer was stopped (it'd hold up what's said)
                        if stop.is_set():
                            return
                        prepare(sentence)
                    q.put(sentence)
            except BaseException as e:  # noqa: BLE001 - the model's error is the turn's, raised where it reads
                q.put(e)
            finally:
                q.put(done)

        threading.Thread(target=read, daemon=True, name="answer-ahead").start()
        try:
            while (item := q.get()) is not done:
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            with gate:
                stop.set()
                getattr(self.body, "unprepare", lambda: None)()

    def _receipt_conversation(self, text: str) -> None:
        """What a turn sent Muse Spark: the words, and the earlier exchanges that go with them, word for word."""
        self.screen.sent("Muse Spark", text)
        for asked, said in self.history:
            self.screen.sent("Muse Spark (earlier in this conversation)", f"{asked} / {said}")

    def privacy_today(self, on_screen: bool = True) -> str:
        """What left the house today, from the privacy receipts' own counts: said, and shown on the TV. Counted and
        answered on this computer, so asking what went to the cloud sends nothing to it. on_screen: the card stays
        (False when the rest of the request will show something else)."""
        d = self.screen.day()
        self._source, self._reason = "device", "counted on this computer from today's privacy receipts"
        midnight = _now(lambda: d.since).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        when = "Today" if d.since <= midnight else f"Since I started at {spoken_time(d.since)}"
        stayed, to = d.turns - d.went, sorted(d.to, key=lambda f: -d.to[f])
        rows = [("✓", f"{_n(stayed, 'request')} answered on this computer: nothing sent")] if stayed else []
        rows += [("→", f"{f}: words from {_n(d.to[f], 'request')}") for f in to]
        if d.words:
            rows.append(("→", f"{_n(d.words, 'word')} in all, each one shown on its turn's receipt"))
        if d.screenshots:
            rows.append(("→", f"{_n(d.screenshots, 'screenshot')} of web pages you asked to see"))
        if d.pictures:
            rows.append(("!", f"{_n(d.pictures, 'camera picture')} of the staged scene, to SAM 3.1"))
        rows.append(("✓", "No sound left the house" if d.pictures else "No camera pictures and no sound left the house"))
        if not d.went:
            self._privacy_card("Nothing has left this house", rows)
            if d.turns > 1:
                return f"{when}, nothing has left this house: all {d.turns} of your requests were answered on this computer."
            return f"{when}, nothing has left this house."
        self._privacy_card(f"{stayed} of {d.turns} requests stayed in this house", rows)
        names = to[0] if len(to) == 1 else ", ".join(to[:-1]) + " and " + to[-1]
        went = (f"{when}, {stayed} of your {d.turns} requests stayed in this house. For the other {d.went}" if stayed
                else f"{when}, each of your {d.turns} requests needed the cloud. For them")
        shots = f", and {_n(d.screenshots, 'screenshot')} of web pages you asked to see" if d.screenshots else ""
        pictures = (f" {_n(d.pictures, 'camera picture')} of the staged scene went to SAM 3.1; no sound did."
                    if d.pictures else " No camera pictures and no sound left the house.")
        return f"{went}, I sent {_n(d.words, 'word')} to {names}{shots}.{pictures}" + (" It's on the screen." * on_screen)

    def heard_today(self) -> str:
        """"What did you hear today?" / "Are you recording?": how often someone spoke near Andy and how few of those were
        for it, from the day's counts (VoiceLoop counts each utterance, never its words), said and shown on the TV.
        Exact about what happens: every utterance is heard on this computer to listen for the name, what isn't for Andy
        is let go at once, and no sound is ever kept."""
        d = self.screen.day()
        self._source, self._reason = "device", "counted on this computer: how often someone spoke, never what was said"
        midnight = _now(lambda: d.since).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        when = "Today" if d.since <= midnight else f"Since I started at {spoken_time(d.since)}"
        rest = d.speech - d.for_andy
        rows = [("✓", f"{_n(d.speech, 'time')} someone spoke near me: heard on this computer, listening for my name"),
                ("✓", f"{d.for_andy} of them for me" + (f"; {rest} let go at once, not a word of them kept" if rest else "")),
                ("✓", "No recording: no sound is ever kept, and none left the house"),
                ("✓", "Kept of what you ask me: only what you ask me to remember, as words")]
        self._privacy_card("What I heard today", rows)
        if not d.speech:
            return f"{when}, I haven't heard anyone speak near me. I never record: no sound is ever kept."
        if not rest:
            return (f"{when}, I heard someone speak near me {_n(d.speech, 'time')}, all of it for me. I never record: no "
                    "sound is ever kept. It's on the screen.")
        return (f"{when}, I heard someone speak near me {_n(d.speech, 'time')}, all on this computer. {d.for_andy} of "
                f"those were for me. The other {rest} I let go at once, and I kept no sound and no words of them. I never "
                "record. It's on the screen.")

    def _privacy_card(self, title: str, rows: list[tuple[str, str]], promises: bool = False) -> None:
        """The day's receipts, or Andy's promises, on the TV in the person's language (the TV follows the language;
        Glimmer on this computer, each line cached): the counts are Andy's own, only the words are translated."""
        if self.language != "en" and self.translator is not None:
            def say(text: str) -> str:  # a line whose numbers came back changed stays in English: a count is never wrong
                said = self.translator.spoken(text, self.language, DISCLOSURE, CRISIS_REPLY)
                return said if re.findall(r"\d+", said) == re.findall(r"\d+", text) else text
            title, rows = say(title), [(mark, say(text)) for mark, text in rows]
        self.screen.privacy_day(title, rows, promises)

    def promises(self) -> str:
        """"What won't you do?": what Andy never does, each with today's receipts, said and shown on the TV. Counted
        and answered on this computer; how many crisis replies there were is nobody's business on a TV, so never shown."""
        d = self.screen.day()
        self._source, self._reason = "device", "Andy's promises, with today's receipts, counted on this computer"
        rows = [("✓", "No camera picture or sound has left this house today" if not d.pictures else
                 f"No sound has left this house; {_n(d.pictures, 'camera picture')} of the staged scene went to SAM 3.1"),
                ("✓", f"No health advice: {_n(d.own_words, 'health question')} answered in my own words today, never a "
                      "model's" if d.own_words else "No health advice: a health question gets my own words, never a model's"),
                ("✓", f"Llama Guard 3 read {_n(d.answers_read, 'sentence')} of the models' answers before I said them"
                      if d.answers_read else "Llama Guard 3 reads every answer a model writes before I say it"),
                ("✓", "Crisis words get the 988 line from my code, before any model"),
                ("✓", f"Every word sent to the cloud is on its receipt: {_n(d.words, 'word')} today" if d.words else
                      "Nothing I was told has gone to the cloud today"),
                ("✓", "I say I'm an AI at the start of every conversation")]
        self._privacy_card("What I never do", rows, promises=True)
        today = ("no camera picture has left this house today" if not d.pictures else "no sound has left this house today")
        return ("I never send a camera picture of your home to the cloud, I never give health advice, and I always say "
                f"I'm an AI. And {today}. It's on the screen, with the receipts.")

    def look_up(self, question: str) -> str:
        if not self.online or self.spark is None:
            self._source, self._reason = "device", "offline: no web search"
            return "I can't look things up right now, because I'm not connected."
        self.say("Let me look that up.")  # a web answer takes a few seconds
        self.screen.doing("Working", "Looking it up")
        try:
            self.screen.sent("Muse Spark + web search", (f"(home: {self.home}) " if self.home else "") + question)
            ans = answers.ask(self.spark, question, budget=self.budget, home=self.home)
        except CLOUD_TROUBLE:
            self._source, self._reason = "device", "the web search didn't answer"
            return "I couldn't look that up just now. Please try again in a little while."
        self._source, self._reason = "cloud", "web search (Muse Spark)"
        self.screen.used("Muse Spark + web search", "cloud")
        if self._advice(question, ans.text):  # the web's answer is read as health advice: Andy's own words instead
            self._reason += "; Llama Guard 3 read health advice in the answer, so Andy's own words instead"
            return HEALTH_REPLY
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

    def chime(self, name: str, even_when_quiet: bool = False) -> None:
        """One of Andy's sounds (voice/earcons.py), before its words: "heard", "found", "reminder", "noticed". Not while
        Andy is asked to be quiet, except a reminder, which was asked for; never if sounds are turned off."""
        c = getattr(self.body, "chime", None)
        if c is None or not self.sounds or (self.quiet() and not even_when_quiet):
            return
        try:
            getattr(self.body, "wait_said", lambda: None)()  # after anything still being said ("Let me look."), not over it
            self.hood.sound()
            c(name)
        except Exception:  # noqa: BLE001 - a sound is never worth a failed turn
            pass

    def emote(self, name: str) -> None:
        """One of Pollen's recorded emotions (robot/reachy_mini.py emote), at a calm moment only: not while quiet, not
        when asked to move less, never while searching or pointing (the callers are the calm moments)."""
        e = getattr(self.body, "emote", None)
        if e is None or self.quiet() or self.liveliness < 0.65:
            return
        try:
            e(name)
        except Exception:  # noqa: BLE001 - a feeling is never worth a failed turn
            pass

    def emergency_turn(self, text: str) -> str:
        """Someone says they've fallen, or can't breathe: 911 first, in Andy's own words (by hand in each language),
        then what a robot that finds things can do at once: find their phone and point at it, so they can call. It
        never watches for falls and claims no safety: it acts only on what it's told (docs/crisis-protocol.md)."""
        self._source, self._reason = "device", "an emergency said: 911 first, in Andy's own words, then its phone found"
        self.screen.own_words()
        self.face_person_to_speak()
        self.say(EMERGENCY_REPLY)
        self._said.append(EMERGENCY_REPLY)
        self._urgent = True  # no "oops" sound if the phone isn't in sight
        try:
            words = self.find("phone", text, opening=False)
        finally:
            self._urgent = False
        self._source, self._reason = "device", "an emergency said: 911 first, in Andy's own words, then its phone found"
        return f"{EMERGENCY_REPLY} {words}"

    def find(self, thing: str, request: str, hint: bool = False, opening: bool = True) -> str:
        """A plain "where are my keys" gets the fast fixed sweep; a request with a hint gets an agent that uses it.
        opening: say "Let me look." (not when the turn has already said what Andy is doing)."""
        told = None if hint else self._told_first(thing)
        if told:
            return told
        self.screen.clear()
        self.screen.timer_start()
        checks = getattr(self.judge, "calls", 0)
        self.finder.looks, self.finder.passed, self._alike, self._not_yours = 0, [], None, False
        self.screen.looking(thing)
        if not self._background and opening:
            self.say("Let me look.", soon=True)  # answer at once, and start looking while it's said
        try:  # where the person is, while Andy still faces them: so the answer can be given from their side
            self._listener = self._measure_listener()
        except (LocalUnavailable, RuntimeError, IndexError):
            self._listener = None
        self.screen.doing("Working", "Looking around the room")
        self.gesture("thinking")
        try:
            return self._find(thing, request, hint, checks)
        finally:
            self.gesture("idle")
            self._listener = None

    def _find(self, thing: str, request: str, hint: bool, checks: int) -> str:
        found, words = None, ""
        for client, model, paid, source, reason in (self.planners() if hint else []):
            tools = SearchTools(self.finder, self.places, self.judge, on_tool=self._tool_moves)
            tools.meant(thing)
            on_look, self.finder.on_look = self.finder.on_look, None  # the plan's own steps show the progress
            try:
                if paid:
                    self.screen.sent("Muse Spark (plans the search)", request)
                with self.hood.span("plan", "Muse Spark" if paid else "Muse Glimmer"):
                    plan = plan_search(client, request, tools, model=model, budget=self.budget, paid=paid)
            except CLOUD_TROUBLE as e:
                self.screen.step(f"{model} is unavailable ({type(e).__name__})")
                continue
            finally:
                self.finder.on_look = on_look
            for tool, _args, result in plan.steps:
                self.screen.step(f"{tool}: {result}")
                if paid:
                    self.screen.sent("Muse Spark (plans the search)", f"{tool}: {result}")
            found, words = tools.pointed, ""  # found: Andy's words come from the tools, never the model's guesses
            self.screen.used(("Muse Spark" if paid else "Muse Glimmer") + " (plans)", source, plan.calls)
            self._source, self._reason = source, reason
            if found is None:
                self.screen.timer_stop()
                said = PLACE_NUMBERS.sub("", plan.reply).strip()
                return said if said[:1].isupper() else self._not_found(thing)  # a sentence the numbers began: ours
            break
        if found is None:
            self._source, self._reason = "device", "fixed search on this computer"
            last = None if self._by_sound is not False else self.places.last_seen(thing, now=self.clock())
            usual = None if self._by_sound is not False else self.places.usual(thing)
            home = None if self._by_sound is not False else self.places.home(thing)
            if home:  # where it lives, as the person said, before where it has happened to be
                usual = {**home, "near": self.places.home_words(thing) or "at home", "count": 0, "of": 0}
            self.screen.step("recall: " + (f"last seen {side(last[0])}" if last else "no recent sighting")
                             + (f"; usually {usual['near'] or side(usual['yaw'])}" if usual else ""))
            self.gesture("searching")
            if self.answer_while_pointing and not self._background and self._by_sound is False and not self._no_promise:
                self.finder.on_confirmed = self._answer_early
            try:
                found = self.finder.find(thing, last, (usual["yaw"], usual["pitch"]) if usual else None)
            finally:
                self.finder.on_confirmed = None
            looks = "once" if self.finder.looks == 1 else f"{self.finder.looks} times"
            self.screen.step(f"looked {looks}" + (f"; {self.finder.why}" if self.finder.why else ""))
        self.screen.timer_stop()
        self.screen.used("SAM 3.1", self.vision_where, self.finder.looks)
        self.screen.used("Muse Glimmer (picture check)", "device", getattr(self.judge, "calls", 0) - checks)
        if found is None:
            return self._not_found(thing)
        early, self._early = (self._early if self._early and self._early[0] is found else None), None
        if not early:
            self._measure(found)
        self.places.saw(found.label, found.yaw, found.pitch, when=self.clock(), metres=found.metres, how="found")
        self._note_place(found.label, found.frame, found.mask)
        self._pointed = True
        self._guide_from = (found, self._listener, self.clock())  # "help me reach it" next starts from here
        self.lost.drop(found.label)  # found: no need to keep looking
        self.screen.doing("Pointing", f"At your {found.label}")
        if found.aim_deg is not None:  # the check after pointing: did it land?
            self.screen.step(f"checked: pointing at it, {found.aim_deg:.0f}° off the middle"
                             + (" after aiming again" if found.reaimed else ""))
        self.gesture("found")
        words = words or (early[1] if early else self._found_words(found))
        self.screen.found(found, words)  # the TV's Reveal starts (or, answered early, gets the checked aim)...
        if early:
            early[2].join()  # the answer, said while the head pointed and checked: done before the turn ends
        else:
            self.chime("found")  # ...as Andy's "there it is!" sound plays, before the words
        return words + ("" if self._background else self._offer_to_watch(found.label, (found.yaw, found.pitch)))

    def _answer_early(self, found: Found) -> None:
        """Confirmed, not yet pointed: say so now, while the head turns to point and checks its aim, as a person points
        and speaks at once. How far is measured first (MapAnything, about 0.2 s): the words say it. On the robot this
        moved the words about 7 s earlier (research.md section 50)."""
        self.screen.timer_stop()  # found: the TV's "to find it" stops here
        self._measure(found)
        words = self._found_words(found)
        self.screen.doing("Pointing", f"At your {found.label}")
        self.screen.found(found, words)  # the Reveal, with the found note
        self._said.append(words)
        self._answered = True
        say = threading.Thread(target=lambda: (self.chime("found"), self.say(words)), daemon=True, name="answering")
        self._early = (found, words, say)
        say.start()

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
        offer = (not self.filming and len(entry["at"]) >= times and thing not in self.places.watching()
                 and now - entry["offered"] > within_s)
        if offer:
            entry["offered"] = now
            self._offered = (thing, now, *where)  # a yes or no answers it
        write_private(path, json.dumps(asked))  # what the person asked for: theirs only, like places.json
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
        lang = LANGUAGES[self.language]
        self.screen.language = f"{lang.native} · {lang.here}" if self.language != "en" else ""
        self.screen.lang = self.language
        if self.language != "en" and self.translator is not None and getattr(self.screen.words, "language", "") != self.language:
            self.screen.words = TVWords(self.translator, self.language)

    def _tv(self, english: str, spanish: str) -> str:
        """A line for the TV in the person's language: Spanish as written, others translated in the background."""
        if self.language == "en":
            return english
        if self.language == "es":
            return spanish
        return self.screen.words(english) if self.screen.words else english

    def set_language(self, to: str) -> str:
        """"Andy, habla español" / "speak English": hearing, voice and captions switch, and it's remembered."""
        if to != "en" and self.translator is None:
            return "I can only speak English on this computer for now."
        if self.voice is not None:
            self._own_voice  # noqa: B018 - the voice it was started with, remembered before the first switch
        if to == self.language:
            if self.clock() - getattr(self, "_switched_at", float("-inf")) <= 15:
                return ""  # "安迪，说中文": the voice loop noticed it and said so; the words themselves ask it again
            return "Okay." if to == "en" else f"I'm already speaking {LANGUAGES[to].name}."
        self.language, self._switched_at = to, self.clock()
        if self.voice is not None:
            self.voice.voice = LANGUAGES[to].voice if to != "en" else self._own_voice
        self.screen.notice(LANGUAGES[to].native or "English")
        self._tv_language()
        self.save_voice()
        self._source, self._reason = "device", "hearing and speaking switched, on this computer"
        return f"Okay, I'll speak {LANGUAGES[to].name} now."  # said in it, by hand (companion/languages.py)

    def language_from_tv(self, to: str) -> None:
        """The TV's settings: a language chosen from its list (screen/server.py, from the TV's own page only). As
        "Andy, speak Korean" does: hearing, voice and the TV switch, it's remembered, and Andy says so, in it."""
        with self.lock:  # after any turn running now, never in the middle of one
            words = self.set_language(to)
            if words:
                self.say(words)

    def notice_language(self, to: str) -> None:
        """Someone called Andy in another of its languages (the voice loop heard it, listening again without one):
        switch to it and say so, in it and by hand ("好的，我现在说中文。"), before answering what they asked."""
        with self.lock:
            line = self.set_language(to)
            self.screen.used("Omnilingual ASR (hearing, which language)", "device")
            if line.startswith("Okay, I'll speak"):
                self.say(line)

    def save_voice(self) -> None:
        path = self.places.path.parent / "voice.json"
        saved = {"liveliness": self.liveliness, "language": self.language, "hey_only": self.hey_only}
        if self.voice is not None:
            saved.update(speed=self.voice.speed, loudness=self.voice.loudness)
        write_private(path, json.dumps(saved))

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
            self.hey_only = bool(saved.get("hey_only", False))
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
                if paid:
                    self.screen.sent("Muse Spark (agent)", f"{tool}: {result}")
            if paid:
                self.screen.sent("Muse Spark (agent)", where_they_live(self.home))
            name = "Muse Spark" if paid else "Muse Glimmer"
            self.screen.used(f"{name} (agent)", where, turn.calls)
            self._source = where
            self._reason = f"{name} planned it with Andy's abilities ({len(turn.steps)} steps)"
            return self._without_advice(request, turn.reply or "Done.")
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

    def film(self, kind: str, number: str = "") -> str:
        """Filming mode, for the demo's takes. "We're filming": Andy's own initiatives wait (looking around for watched or
        lost things, the evening home check, holding still to notice, offers to keep an eye on things), the TV stays
        awake; reminders still come, as they were asked for. "Take two": no words (the take starts clean) but a clap,
        the TV flashing "TAKE 2", and its exact time written to film/takes.json, so make_film.py sync can line the TV's
        recording up with the camera. "Cut" says how long the take ran; "that's a wrap" ends it."""
        now = time.time()
        if kind == "film_on" or (self.filming is None and kind == "take"):
            self.filming = self.filming or {"since": now, "takes": []}
            self.screen.filming(True)
            if kind == "film_on":
                return ("Filming mode: my own initiatives wait until you're done, so nothing interrupts a take. Say 'take "
                        "one' and I'll clap to mark it.")
        if self.filming is None:
            return "We're not filming. Say 'we're filming' first."
        takes = self.filming["takes"]
        if kind == "take":
            n = int(number) if number.isdigit() else (takes[-1]["take"] + 1 if takes else 1)
            self.screen.flash(f"TAKE {n}")
            take = {"take": n, "clap": round(time.time(), 3), "heard": False, "seconds": None}
            c = getattr(self.body, "chime", None)
            if c:
                c("clap")  # even when sounds are off: it's the mark the edit lines up on
            takes.append(take)
            self._film_save()
            if hasattr(self.body, "heard_lately"):  # when it came out of the speaker, by Andy's own ears, meanwhile
                threading.Thread(target=self._clap_heard, args=(take, self.filming), daemon=True).start()
            return ""  # nothing said: the take starts clean
        if kind == "cut":
            if not takes or takes[-1]["seconds"] is not None:
                return "Cut, but no take was running. Say 'take one' to start one."
            t = takes[-1]
            t["seconds"] = round(now - t["clap"], 1)
            self._film_save()
            m, sec = divmod(int(t["seconds"]), 60)
            return f"Cut: take {t['take']}, {f'{m} minute{chr(115) * (m != 1)} ' if m else ''}{sec} second{'s' * (sec != 1)}."
        n = len(takes)
        self.filming = None
        self.screen.filming(False)
        return (f"That's a wrap: {n} take{'s' * (n != 1)}, listed in film/takes.json. I'm back to my usual self."
                if n else "That's a wrap. I'm back to my usual self.")

    def _clap_heard(self, take: dict, session: dict, wait_s: float = 2.0) -> None:
        """The clap's time as Andy's microphones heard it: the speaker starts a sound about two thirds of a second after
        it's sent (0.52 to 0.77 s on the robot, evals/filming.py), too late to line a recording up on the time it was
        sent. Found in the microphones' last few seconds, within 1.5 s of being sent."""
        from .voice.earcons import RATE, find, sound

        time.sleep(wait_s)
        samples, start = self.body.heard_lately(around=take["clap"])
        if samples is None:
            return
        a = int((take["clap"] - start - 0.2) * RATE)
        if a < 0:
            return
        found = find(samples[a: a + int(1.7 * RATE) + len(sound("clap"))], "clap")
        if found and found[0][1] >= 0.15:  # on the robot its own clap matches 0.24 to 0.56 (its microphones damp what it plays)
            take["clap"], take["heard"], take["match"] = round(start + a / RATE + found[0][0], 3), True, found[0][1]
            self._film_save(session)

    def _film_save(self, session: dict | None = None) -> None:
        session = session or self.filming
        try:
            self.film_log.parent.mkdir(parents=True, exist_ok=True)
            log = json.loads(self.film_log.read_text()) if self.film_log.exists() else {"sessions": []}
            log["sessions"] = [s for s in log["sessions"] if s["since"] != session["since"]] + [session]
            self.film_log.write_text(json.dumps(log, indent=1))
        except (OSError, ValueError):
            pass  # the takes still happened; only the list is missing

    def _services(self) -> list[dict]:
        """For /hood: each local service and whether it answers, at most every 5 s (the page asks every second)."""
        from .companion.selfcheck import ping

        at, last = self._services_at
        if time.monotonic() - at < 5.0:
            return last
        out = []
        for name, model, obj, path in (("Seeing", "SAM 3.1", self.segmenter, "/health"),
                                       ("How far", "MapAnything", self.depth, "/health"),
                                       ("Thinking", "Muse Glimmer", self.device, "/models"),
                                       ("Hearing and speaking", "Omnilingual ASR · SeamlessM4T v2", self.voice, "/health"),
                                       ("Safety", "Llama Guard 3", self.guard, "/health")):
            endpoint = getattr(obj, "endpoint", None)
            if not endpoint:
                continue
            try:
                out.append({"name": name, "model": model, "ok": True, "ms": round(ping(endpoint + path, timeout=1.5))})
            except Exception:  # noqa: BLE001 - not answering is what the page is for
                out.append({"name": name, "model": model, "ok": False, "ms": None})
        self._services_at = (time.monotonic(), out)
        return out

    def check_myself(self) -> str:
        """"Are you OK?": each part Andy needs, checked and timed (companion/selfcheck.py); the TV lists them, and Andy
        says what works, what doesn't, and what it can still do."""
        self.screen.clear()
        self.screen.doing("Working", "Checking myself")
        self.gesture("thinking")
        try:
            report = self_check(self)
        finally:
            self.gesture("idle")
        self.screen.self_check([{"name": p.name, "model": p.model, "status": p.status, "detail": p.detail}
                                for p in report.parts], report.seconds)
        self._source = "device"
        self._reason = f"checked {len(report.parts)} parts of myself, on this computer, in {report.seconds:.1f} s"
        return self_summary(report)

    def remember_told(self, thing: str, where: str) -> str:
        """"I'm putting my passport in the top drawer of the desk": the words kept (memory/told.py), said back."""
        where = yours(where)
        self.told.tell(thing, where)
        self.screen.told(thing, where, "just now")
        self._source, self._reason = "device", "your words, kept on this computer"
        return f"Got it: your {thing}, {where}. I'll remember."

    def _told_first(self, thing: str) -> str | None:
        """Where the person said they put it, if they did and the camera hasn't seen it since: at once, without moving.
        Asked again within a few minutes, None: then Andy looks around the room."""
        if self._background or self._by_sound is not False or self._no_promise:
            return None
        note = self.told.latest(thing)
        seen = self.places.seen_at(thing)
        if not note or (seen and seen > note["at"]):
            return None
        if self._told_given and self._told_given[0] == thing and self.clock() - self._told_given[1] <= TOLD_AGAIN_S:
            self._told_given = None
            return None
        self._told_given = (thing, self.clock())
        when = self._when(note["at"])
        self.screen.told(thing, note["words"], when)
        self._source, self._reason = "device", "what you told me, kept on this computer"
        them = _it(thing) == "them"
        return (f"You told me {when}: your {thing} {'are' if them else 'is'} {note['words']}. If {'they are' if them else 'it is'}"
                f"n't there, ask me again and I'll look around the room.")

    def set_home(self, thing: str) -> str:
        """"My keys live here": where Andy sees them now becomes their home (memory/places.py), and Andy keeps an eye on
        them. A search then looks there first, "Is everything home?" checks, and so does Andy each evening."""
        self.places.watch(thing)  # a thing with a home is kept an eye on
        self.finder.last_found, self._no_promise = None, True
        try:
            self.find(thing, f"where are my {thing}")
        finally:
            self._no_promise = False
        f = self.finder.last_found
        if f is None:
            return f"I can't see your {thing} from here. Put {_it(thing)} where {_lives(thing)}, where I can see, and tell me again."
        near = ""
        where_near = getattr(self.judge, "where_near", None)
        if where_near:
            try:
                near = where_near(f.frame, f.mask) or ""
            except Exception:  # noqa: BLE001 - the home is kept by its direction anyway
                near = ""
        self.places.set_home(thing, f.yaw, f.pitch, f.metres, near, when=self.clock())
        self.refresh_panels()
        return (f"Got it: your {thing} {'live' if _it(thing) == 'them' else 'lives'} {near or side(f.yaw)}. Ask me "
                f"'is everything home?' any time, and I'll check every evening at {HOME_CHECK_HOUR - 12}.")

    def home_check(self, evening: bool = False) -> str:
        """"Is everything home?": one look at each thing's home; a thing that isn't there is searched for, pointed at,
        and then its home is pointed at ("It lives there"); a thing not seen anywhere is looked for again later
        (memory/lost.py). The TV shows each one: home, away (where it is and where it lives), or not seen."""
        homes = self.places.homes()
        if not homes:
            return "None of your things has a home yet. Put your keys where they live, and say: my keys live here."
        self.screen.clear()
        if not evening:
            self.say("Let me check.", soon=True)
        home, away, missing, rows = [], [], [], []
        self.gesture("searching")
        try:
            for thing, h in homes.items():
                there = self.finder.confirm(thing, h["yaw"], h["pitch"])  # one look at where it lives
                lives = self.places.home_words(thing) or side(h["yaw"])
                if there:
                    home.append(thing)
                    self.places.saw(thing, there.yaw, there.pitch, when=self.clock(), how="found")
                    rows.append({"thing": thing, "status": "home", "home": lives})
                    continue
                self.finder.last_found, self._background = None, True
                try:
                    self.find(thing, f"where are my {thing}")
                finally:
                    self._background = False
                f = self.finder.last_found
                if f:
                    now = (f"{f.for_you['words']}" if f.for_you else
                           side(f.yaw) + (f", {how_far(f.metres, metric=self.language != 'en')}" if f.metres is not None else ""))
                    away.append((thing, h, f, now, lives))
                    rows.append({"thing": thing, "status": "away", "now": now, "home": lives})
                else:
                    missing.append((thing, lives))
                    self.lost.add(thing)
                    rows.append({"thing": thing, "status": "missing", "home": lives})
        finally:
            self.gesture("idle")
        self.screen.home_check(rows, evening)
        self.screen.used("SAM 3.1", self.vision_where, len(homes))
        self._source, self._reason = "device", f"looked at the home of each of {len(homes)} things, on this computer"
        self.refresh_panels()
        if not away and not missing:
            self.body.look(0.0, 0.0)
            return ("Everything's home" + (" for the night" if evening else "") + ": " + _join(home) + ".")
        lines = []
        if home:
            lines.append(_join(home)[0].upper() + _join(home)[1:] + (" are" if len(home) > 1 or _it(home[0]) == "them" else " is") + " home.")
        steps = []
        for thing, h, f, now, lives in away:
            them = _it(thing) == "them"
            steps.append(((f.yaw, f.pitch), f"Your {thing} {'aren' if them else 'isn'}'t home: {'they are' if them else 'it is'} {now}."))
            steps.append(((h["yaw"], h["pitch"]), f"{'They live' if them else 'It lives'} there, {lives}."))
        for thing, lives in missing:
            them = _it(thing) == "them"
            steps.append((None, f"I can't see your {thing} anywhere; {'they live' if them else 'it lives'} {lives}. I'll keep looking."))
        if lines:
            self.say(lines[0])
        for i, (at, words) in enumerate(steps):
            if at:
                self.body.point(*at)
            if i < len(steps) - 1:
                self.say(words)
        return steps[-1][1]

    def find_by_sound(self, thing: str = "") -> str:
        """"I'm ringing my phone": turn to the ringing (companion/sound.py turn_to), then look that way with SAM 3.1,
        and if it can't be seen there (under a cushion), point where the sound is."""
        thing = thing or "phone"
        if self.ear is None:
            return f"I can only follow a sound with the robot's microphones. Ask me where your {thing} is, and I'll look."
        floor = self.ear.floor()  # the room's own noise, from the last few seconds, before it rings
        self._stop_following.clear()
        self.following = True  # the face tracker leaves the head alone while it turns to the sound
        self.say("Ring it now, and I'll turn to the sound." if thing in RINGS else
                 f"Make your {thing} beep now, and I'll turn to the sound.")
        self.screen.listening(thing, [], None)
        self.gesture("searching")  # still: the motors mustn't be what it hears

        def turn(yaw):
            self.body.look(yaw, 0.0)
            self.wait(0.5)

        def listen():
            if self._stop_following.is_set():
                return None
            t = self.ear.clock()
            self.wait(1.6)
            return reading(self.ear.since(t), floor)

        try:
            turn(getattr(self.body, "yaw", 0.0))
            if not wait_for(listen):  # the person dials meanwhile: up to WAIT_S for it to start ringing
                yaw, steps = None, []
            else:
                yaw, steps = turn_to(listen, turn, getattr(self.body, "yaw", 0.0),
                                     on_step=lambda y, s, st: self.screen.listening(thing, st, None))
        finally:
            self.following = False
            self.gesture("idle")
        self.screen.listening(thing, steps, yaw, done=True)
        if yaw is None:
            return f"I didn't hear it ring. Is the sound on? Ring it again, and say: I'm ringing my {thing}."
        views, behind = self.finder.views, getattr(self.finder, "behind", ())
        self.finder.views, self.finder.behind = fan(yaw), ()
        self.finder.last_found, self._background, self._by_sound = None, True, yaw
        try:
            words = self.find(thing, f"where is my {thing}")
        finally:
            self.finder.views, self.finder.behind = views, behind
            self._background = self._by_sound = False
        self._source = "device"
        self._reason = f"the robot's microphones heard the ringing {side(yaw)} ({len(steps)} turns); SAM 3.1 looked there"
        if self.finder.last_found is not None:
            return "I followed the ringing. " + words
        self.body.point(yaw, 15.0)
        return (f"I can hear it, but I can't see it. It's ringing {side(yaw)}, where I'm pointing: "
                f"it may be under something.")

    def stop_looking(self, text: str, found: bool) -> str:
        """"I found my keys" / "stop looking for the wallet": let go of what Andy was still looking for (a thing named,
        or all of it). Said of something Andy wasn't looking for, it's just good news."""
        lost = self.lost.looking()
        named = [t for t in lost if re.search(r"\b" + re.escape(t) + r"\b", text, re.I)]
        gone = [g for t in (named or lost) for g in self.lost.drop(t)]
        self.refresh_panels()
        if found:
            return f"Glad {_join(gone) if named else 'it'} turned up!" if gone else "Glad you found it!"
        if not gone:
            return "I wasn't looking for anything just now."
        return f"Okay, I'll stop looking for {_join(gone)}."

    def guide_hand(self, thing: str = "", seconds: float = 40.0) -> str:
        """"Help me reach it": talk the person's hand onto the thing just found, from their side (companion/guide.py),
        until the hand is on it, "stop", or 40 s. A thing that wasn't just found is found first."""
        recent = self._guide_from if self._guide_from and self.clock() - self._guide_from[2] <= GUIDE_AFTER_S else None
        thing = thing or (recent[0].label if recent else "")
        if not thing:
            return "Which thing shall I guide your hand to? Say, for example: guide my hand to my keys."
        if recent is None or recent[0].label != thing:
            self._guide_from = None
            words = self.find(thing, f"where are my {thing}")
            if self._guide_from is None:
                return words  # not found, and the find said so
            self.say(words)
            recent = self._guide_from
        else:
            self.body.look(recent[0].yaw, recent[0].pitch)  # eyes back on it: the head may have turned to the person
        found, listener, _ = recent
        # where the person is on the plan: measured at the find, or else where their voice came from, about a metre off
        person = on_plan(*listener) if listener else on_plan(self.person[0] if self.person else 0.0, 0.0, 1.0)
        self._stop_following.clear()
        self.following = True  # the face tracker leaves the head on the thing
        self.say("Put your hand out toward it, and I'll guide you.")
        self.screen.doing("Guiding", f"Your hand to your {thing}")
        frames = [0]

        def shown(frame, mask, hand, words, way, metres):
            frames[0] += 1
            self.screen.guiding(thing, frame, mask, hand, words, way, metres)

        try:
            r = guide(self.body, self.finder.segmenter, thing, (found.yaw, found.pitch),
                      height_above(found.pitch, found.metres), person, self.say,
                      lambda name: self.chime(name, even_when_quiet=True), shown, self._stop_following.is_set, seconds,
                      cam=self.finder._cam, clock=self.clock, wait=self.wait)
        finally:
            self.following = False
            self.screen.doing("Waiting")
        self.screen.used("SAM 3.1", self.vision_where, frames[0])
        self._source = "device"
        self._reason = f"SAM 3.1 watched your hand and your {thing} ({frames[0]} frames), on this computer"
        is_ = "are" if _it(thing) == "them" else "is"
        if r.why == "there":
            self.chime("found")
            self.gesture("nod")
            self.screen.guided("That's it!")
            return f"That's it! Your {thing} {is_} right at your fingertips."
        self.screen.guided("")
        where = found.for_you["words"] if found.for_you else side(found.yaw)
        return {"no hand": "I couldn't see your hand. Come a little closer, and say: guide my hand.",
                "lost": f"I've lost sight of your {thing}. Ask me where {_it(thing)} {is_}, and I'll look again.",
                "stopped": "Okay, I've stopped.",
                "time": f"Let's stop there. Your {thing} {is_} {where}."}[r.why]

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
        if self._by_sound is not False:  # by its sound: only a thing near where it rang
            yaw = pixel_to_angles(*mask.center, frame.yaw, frame.pitch, self.finder._cam(frame))[0]
            if apart(yaw, self._by_sound) > HEARD_WITHIN_DEG:
                self.finder.rejected = "one that wasn't where the ringing is"
                return False
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
        guard = getattr(self.segmenter, "guard", None)  # Llama Prompt Guard 2, on this computer

        def step(jpeg, words, point):
            self.screen.web(jpeg, first, words, point, url=self._browser.url())

        try:
            if more:
                previous = self._web[1]  # None after a run that stopped early: its last step was never answered
                task = request if previous else f"{request} (The browser shows the page for: {first}.)"
                self.screen.sent("Muse Spark (uses the web)", request)
                run = web.use_the_web(self.spark, self._browser, task, step, previous=previous, budget=self.budget,
                                      max_steps=2, within_s=40.0, shots=shots, guard=guard)
            else:
                self.screen.sent("Muse Spark (web search)", (f"(home: {self.home}) " if self.home else "") + request)
                url = web.best_page(self.spark, request, self.home, budget=self.budget)
                self._browser.open(url) if url else self._browser.search(request)
                self.screen.used("Muse Spark (web search)", "cloud")
                run = web.use_the_web(self.spark, self._browser, web.SHOW.format(task=request, url=url or "search results"),
                                      step, budget=self.budget, max_steps=3, within_s=45.0, shots=shots, guard=guard)
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
                self.screen.screenshots_sent("Muse Spark (computer use)", shots[0])
                self.screen.used("Muse Spark (computer use)", "cloud", shots[0])
        self._web = (first, None if run.stopped else run.response_id, self.clock())
        if run.guarded:
            self.screen.used("Llama Prompt Guard 2 (reads the page)", "device", run.guarded)
        if "instructions aimed at me" in run.stopped:
            return "That page had instructions aimed at me, so I stopped there and didn't follow them."
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
            self.screen.sent("Muse Spark + web search", (f"(home: {self.home}) " if self.home else "") + question)

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
                    self.places.saw(label, found.yaw, found.pitch, when=self.clock(), how="found")
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
        self.emote("welcoming2")  # a wave goodbye
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
                                    Mask("what you're holding", box, None, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)),
                                    looks=1),
                              seen or "")
        return seen or "I couldn't get a good look. Could you hold it a little closer to me?"

    def stop_following(self) -> None:
        self._stop_following.set()

    def _tool_moves(self, starting: bool) -> None:
        """Still while a tool looks; thinking while the model decides what to do next."""
        self.gesture("searching" if starting else "thinking")

    def scan_room(self) -> str:
        """"Show me the room": five looks across the room, SAM 3.1 marking the person's things in each, and MapAnything
        joining them into the room's shape in 3D, on this computer. The TV shows the shape only, never a colour or a
        picture, for two minutes; the frames are dropped once measured. Watched things get their place and distance."""
        if self.depth is None or not hasattr(self.body, "capture"):
            return "I can't measure the room right now."
        labels = list(dict.fromkeys(self.places.watching() + list(ROOM_THINGS)))[:8]  # the server takes 8 a frame
        self.screen.clear()
        self.screen.timer_start()
        self.screen.looking("room")  # the TV: "Measuring the room in 3D", each look live
        self.say("Let me look around the room.", soon=True)
        self.screen.doing("Working", "Measuring the room")
        self.gesture("searching")
        looks, many = [], getattr(self.segmenter, "find_many", None)
        try:
            for yaw in ROOM_VIEWS:
                if not self.body.reach.allows(yaw, ROOM_PITCH):
                    continue
                self.body.look(yaw, ROOM_PITCH, precise=False)
                frame = self.body.capture()
                found = many(frame, labels) if many else {label: self.segmenter.find(frame, label) for label in labels}
                masks = [m for ms in found.values() for m in ms if (m.score if m.score is not None else 0.5) >= 0.6]
                self.screen.glimpse(frame, masks)
                self.screen.step(f"looked {side(frame.yaw)}: " + (", ".join(sorted({m.label for m in masks})) or "nothing of yours"))
                looks.append((frame, self.finder._cam(frame), masks))
            self.screen.doing("Working", "Joining the views in 3D")
            out = self.depth.scan(looks)
        except (LocalUnavailable, RuntimeError):
            return "I couldn't measure the room just now."
        finally:
            looks.clear()  # the frames: measured, then gone
            self.gesture("idle")
            self.screen.timer_stop()
        things = room_things(out["things"])
        self.screen.used("SAM 3.1", self.vision_where, len(ROOM_VIEWS))
        self.screen.used("MapAnything (the room in 3D)", "device")
        self.screen.step(f"MapAnything: {out['n']:,} points of shape in {out.get('seconds', 0):.1f} s")
        self.screen.room(millimetres(out["points"]), things, out.get("seconds", 0.0))
        self.chime("found")
        watched = set(self.places.watching())
        for t in things:
            if t["label"] in watched:
                self.places.saw(t["label"], t["yaw"], t["pitch"], when=self.clock(), metres=t["metres"], how="scanned")
        self.refresh_panels()
        named = sorted(things, key=lambda t: (t["label"] not in watched, t["metres"]))[:3]
        metric = self.language != "en"
        said = "; ".join(f"your {t['label']} {side(t['yaw'])}, {how_far(t['metres'], metric=metric)}" for t in named)
        return ("Here's the room as I measured it, on the screen" + (f": {said}." if said else ".")
                + " Its shape only, never a picture.")

    # --- the first five minutes: "Andy, let's get started" ---

    @property
    def setup_done(self) -> bool:
        return (self.places.path.parent / "setup.json").exists()

    def start_setup(self) -> str:
        """Andy introduces itself, measures the room, and asks what the person loses most (step 1 of 3)."""
        self.say("Hi, I'm Andy. I find what you've lost and point at it, and what I see and hear stays in this house."
                 + (" First, let me look around the room." if self.depth is not None else ""))
        room = ""
        if self.depth is not None:
            measured = self.scan_room()
            room = "Here's your room, measured in 3D. " if measured.startswith("Here's the room") else ""
        self._setup = {"step": "things", "at": self.clock(), "again": False}
        self.screen.setup("things")
        return room + "Now, what do you lose most often? Your keys, your glasses, your phone, the remote?"

    def _setup_step(self, text: str) -> str | None:
        """The person's answer to the setup's question; None: not for the setup (it ends, and the turn goes on)."""
        if SKIP.match(text):
            self._setup = None
            self.screen.setup(None)
            return "Okay, we'll leave it there. Say 'Hey Andy, let's get started' any time."
        step = self._setup["step"]
        if step == "things":
            things = things_in(text)
            if things:
                return self._setup_watch(things)
            if not self._setup["again"]:
                self._setup.update(again=True, at=self.clock())
                return "Which things? For example, say: my keys and my glasses."
            self._setup = {"step": "try", "at": self.clock(), "thing": "keys"}
            self.screen.setup("try", {"thing": "keys"})
            return "No problem: tell me later with 'keep an eye on my keys'. Now try me: say, 'Hey Andy, where are my keys?'"
        self._setup = None  # step "try": whatever they say is answered as usual, and the setup ends with it
        said = self._answer(text)
        write_private(self.places.path.parent / "setup.json", json.dumps({"done_at": self.clock()}))
        self.screen.setup("done")
        return said + (" You're all set. Pictures and voice stay on the computer beside me: ask me what I sent to the "
                       "cloud today, any time.")

    def _setup_watch(self, things: list[str]) -> str:
        """Step 2 of 3: keep an eye on them, look once for them all, and point at each one seen."""
        for t in things:
            self.places.watch(t)
        self.say("Let me look for " + ("them" if len(things) > 1 else f"your {things[0]}") + ".", soon=True)
        self.gesture("searching")
        try:
            noted = glance(self.body, self.segmenter, self.places, on_seen=self._note_place)
        finally:
            self.gesture("idle")
        for label in [t for t in things if t in noted][:3]:
            self.body.point(*noted[label])
            self.say(f"There {'are' if _it(label) == 'them' else 'is'} your {label}.")
        if noted:
            self.chime("found")
        self.refresh_panels()
        missing = [t for t in things if t not in noted]
        first = next((t for t in things if t in noted), things[0])
        self._setup = {"step": "try", "at": self.clock(), "thing": first}
        self.screen.setup("try", {"thing": first})
        return (f"I'll keep an eye on {_join(things)}."
                + (f" I couldn't see {_join(missing)} just now; I'll notice when I do." if missing else "")
                + f" Now try me: say, 'Hey Andy, where {'are' if _it(first) == 'them' else 'is'} my {first}?'")

    # --- a phone as a remote (screen/remote.py) ---

    def pair_phone(self) -> str:
        """"Andy, connect my phone": six numbers on the TV for three minutes, and where to type them."""
        if self.pairing is None:
            return ("I can't take requests from a phone yet: I have to be started with the remote turned on, on your "
                    "home network.")
        code = self.pairing.new_code()
        self.screen.pairing(self.remote_url, code, self.pairing.code_left())
        return "On your phone, open the address on the TV and type the six numbers. They work for three minutes."

    def forget_phones(self) -> str:
        if self.pairing is None:
            return "No phone can ask me anything: the remote isn't turned on."
        n = self.pairing.forget_all()
        self.screen.pairing("", "", 0)
        return f"Done. I've forgotten {n} phone{'s' if n != 1 else ''}; none can ask me anything now." if n else \
            "No phone was connected, and none can ask me anything."

    def ask_from_phone(self, text: str) -> str:
        """A paired phone's request: a turn like any other, on its own thread, so the phone hears back at once
        ("ok"); "busy" while another turn runs. Andy answers in its room; the phone reads the TV's state."""
        if self._phone_turn or not self.lock.acquire(blocking=False):
            return "busy"
        self.lock.release()
        self._phone_turn = True

        def turn():
            try:
                self.screen.notice("Asked from your phone")
                self.hear(text)
            finally:
                self._phone_turn = False

        threading.Thread(target=turn, daemon=True, name="phone-turn").start()
        return "ok"

    # --- the story of a watched thing, and its habits (memory/places.py): words and directions, never a picture ---

    HOW_SAID = {"found": "I found {it} {where}", "glanced": "I saw {it} {where}, in passing",
                "noticed": "you put {it} down {where}", "scanned": "I saw {it} {where}, measuring the room",
                "seen": "I saw {it} {where}"}

    def _when(self, t: float) -> str:
        now, then = _now(self.clock), dt.datetime.fromtimestamp(t)
        if then.date() == now.date():
            return f"at {spoken_time(t)}"
        if (now.date() - then.date()).days == 1:
            return f"yesterday at {spoken_time(t)}"
        return f"on {then:%A} at {spoken_time(t)}"

    def _where(self, h: dict) -> str:
        far = f", {how_far(h['metres'], metric=self.language != 'en')}" if h.get("metres") is not None else ""
        return (h.get("near") or side(h["yaw"])) + far

    def _not_watched(self, thing: str) -> str | None:
        if thing not in self.places.watching():
            return (f"I'm not keeping an eye on your {thing}. Say 'keep an eye on my {thing}', and I'll remember where "
                    f"{_it(thing)} goes, in words, never a picture.")
        if not self.places.history(thing):
            return f"I haven't seen your {thing} since you asked me to keep an eye on {_it(thing)}."
        return None

    def story(self, thing: str) -> str:
        """"What happened to my keys today?": where they've been, as Andy knew it, newest last; the TV draws it."""
        if (no := self._not_watched(thing)) is not None:
            return no
        it, items = _it(thing), []
        for h in self.places.history(thing):
            line = self.HOW_SAID.get(h.get("how", "seen"), self.HOW_SAID["seen"]).format(it=it, where=self._where(h))
            items.append({"when": self._when(h["since"]), "how": h.get("how", "seen"), "words": line[0].upper() + line[1:],
                          "since": h["since"], "last": h["at"], "gone": h.get("gone")})
            if h.get("gone"):
                items.append({"when": self._when(h["gone"]), "how": "picked up", "words": f"You picked {it} up.",
                              "since": h["gone"], "last": h["gone"]})
        usual = self.places.usual(thing)
        self.screen.timeline(thing, items[-8:], {"words": self._where(usual), "count": usual["count"], "of": usual["of"]}
                             if usual else None)
        low = lambda w: w if w.startswith("I ") else w[0].lower() + w[1:]  # noqa: E731 - "I" stays a capital
        told = [f"{x['when'][0].upper() + x['when'][1:]}, {low(x['words'])}" for x in items[-4:]]
        last = self.places.seen_at(thing)
        tail = (f" I last saw {it} {_ago(self.clock() - last)}." if last and items and items[-1]["how"] != "picked up" else "")
        habit = (f" {'They usually end' if it == 'them' else 'It usually ends'} up {self._where(usual)}."
                 if usual and usual["count"] >= 2 else "")
        return f"Here's the story of your {thing}. " + ". ".join(t.rstrip(".") for t in told) + "." + tail + habit + \
            " It's on the screen."

    def usual_place(self, thing: str) -> str:
        """"Where do I usually leave my keys?": the place it has ended up most often."""
        if (no := self._not_watched(thing)) is not None:
            return no
        usual = self.places.usual(thing)
        if not usual:
            return (f"I haven't seen your {thing} in the same place twice yet. Ask me again in a few days, and I'll "
                    f"know {_it(thing)} better.")
        self.story(thing)  # the TV shows the story, the usual place at its top
        they = "they aren't" if _it(thing) == "them" else "it isn't"
        return (f"Usually {self._where(usual)}: {usual['count']} of the {usual['of']} places I've seen "
                f"{_it(thing)}. If {they} where I last saw {_it(thing)}, that's where I look next.")

    def what_time(self, day: bool = False) -> str:
        """From the clock on this computer, never a model's guess."""
        now = dt.datetime.fromtimestamp(self.clock())
        if day:
            return f"It's {now:%A}, {now:%B} {now.day}."
        return f"It's {spoken_time(self.clock())}."

    def _measure(self, found: Found) -> None:
        """How far away: MapAnything reads the frame the thing was confirmed in, on this computer. Without it (not
        running, or no sure depth there) Andy says the direction only, as before."""
        if self.depth is None:
            return
        try:
            found.metres = self.depth.distances(found.frame, [found.mask], self.finder._cam(found.frame))[0]
        except (LocalUnavailable, KeyError, IndexError):
            return
        self.screen.used("MapAnything (how far)", "device")
        if found.metres is not None:
            self.screen.step(f"MapAnything: {found.metres:.1f} m away")

    def _measure_listener(self) -> tuple[float, float, float] | None:
        """Where the person is (yaw, pitch, metres from Andy's camera): SAM 3.1 finds them where Andy faces now (it
        turned to their voice), MapAnything says how far. None when they aren't in view or can't be measured."""
        if self.depth is None or self.person is None or not hasattr(self.body, "capture"):
            return None
        if abs(getattr(self.body, "yaw", self.person[0]) - self.person[0]) > 40:
            return None  # not facing them now
        frame = self.body.capture()
        people = [m for m in self.segmenter.find(frame, "person") if (m.score if m.score is not None else 0.5) >= 0.5]
        if not people:
            return None
        best, cam = max(people, key=lambda m: m.area), self.finder._cam(frame)
        metres = self.depth.distances(frame, [best], cam)[0]
        if metres is None or not 0.4 <= metres <= 8.0:
            return None
        return (*pixel_to_angles(*best.center, frame.yaw, frame.pitch, cam), metres)

    def _found_words(self, f: Found) -> str:
        where = side(f.yaw) + (f", {how_far(f.metres, metric=self.language != 'en')}" if f.metres is not None else "")
        if self._listener and f.metres is not None and f.reachable:  # from their side: no mirroring, no guessing
            f.for_you = from_them(self._listener, (f.yaw, f.pitch, f.metres))
            if f.for_you:
                where = f"{f.for_you['words']}, at your {f.for_you['clock']} o'clock"
        if not f.reachable:
            return f"I can't turn far enough to point, but your {f.label} is {where}."
        yours = ", the one you showed me" if self._alike is not None and self.mine.knows(f.label) else ""
        home = self.places.at_home(f.label, f.yaw, f.pitch)
        said = f"I see your {f.label}{yours}, {where}." + (" Right at home, where " + _lives(f.label) + "." if home else
                                                           f" Right where I last saw {_it(f.label)}." if f.remembered else
                                                           " Right where you usually leave " + _it(f.label) + "." if f.usual else "")
        opener = FOUND_OPENERS[_it(f.label)][self._finds % len(FOUND_OPENERS["it"])]  # said like a person, in turn
        self._finds += 1
        said = f"{opener} {said}"
        passed = self.finder.passed or []  # what it looked at on the way and passed over: say so, once
        if any("not yours" in why for why in passed):
            said += f" The other {f.label} isn't yours."
        elif any("picture" in why for why in passed):
            said += " Not the picture of one on the screen."
        return said

    def _not_found(self, thing: str) -> str:
        if self._background:
            return ""  # Andy's own second look: nothing to say, and it keeps looking
        if not getattr(self, "_urgent", False):  # never a playful "oops" right after "please call 911"
            self.emote("oops1")
        if self._no_promise:
            return f"I can't see your {thing} from here."
        note = self.told.latest(thing)
        told = (f" {self._when(note['at'])[0].upper() + self._when(note['at'])[1:]}, you told me {_it(thing)} "
                f"{'were' if _it(thing) == 'them' else 'was'} {note['words']}." if note else "")
        again, since = not self.lost.add(thing), self.lost.since(thing)
        looks = self.lost.looks(thing)
        if self.ear is not None and thing in RINGS | BEEPS:
            hint = (f" If you can ring it, say: I'm ringing my {thing}." if thing in RINGS else
                    f" If it has a tracker that beeps, say: listen for my {thing}.")
        else:
            hint = ""
        promise = hint + (f" Still no sign of {_it(thing)}: I've looked {looks} time{'s' if looks != 1 else ''} since "
                   f"{spoken_time(since)}. I'll keep at it." if again and since else
                   f" I'll keep looking, and tell you when I see {_it(thing)}.")
        self.refresh_panels()
        if self._not_yours or "not yours" in self.finder.why:
            return f"I saw a {thing}, but not yours.{promise} Could you tell me where you last had {_it(thing)}?"
        if "picture" in self.finder.why:
            return f"I only saw a picture of {thing} on a screen.{promise} Could you tell me where you last had {_it(thing)}?"
        return f"Hmm, I couldn't find your {thing} from here.{told}{promise} Where did you last have {_it(thing)}?"

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
            metres = self.places.metres(label)
            far = f", {how_far(metres, metric=self.language != 'en')}" if metres is not None else ""
            lines.append(f"{label}: seen {_ago(self.clock() - at)}, {where}{far}{moved}")
        watched = self.places.watching()
        lines += [f"{k}: I know it by sight" for k in self.mine.known() if k not in watched]
        lines += [f"{k}: {n['words']} (you told me {self._when(n['at'])})" for k, n in self.told.all().items()]
        return lines

    # --- noticing (memory/notice.py): the head held still between turns, and given back the moment a turn starts ---

    def begin_noticing(self) -> threading.Event | None:
        """Hold the head still for a noticing clip, unless a turn is running or the body is busy. The event returned
        is set if a turn (or a reminder, or a glance) interrupts the clip."""
        motion = getattr(self.body, "motion", None)
        with self._notice_lock:
            if motion is None or self.filming or not self.lock.acquire(blocking=False):
                return None
            try:
                if motion.mode != "idle":
                    return None
                self._noticing = threading.Event()
                motion.set_mode("searching")  # still, so what moves in the picture is the room
                return self._noticing
            finally:
                self.lock.release()

    def end_noticing(self, cancel: threading.Event) -> None:
        """The clip is over: the head goes back to its idle body language, unless a turn took it already."""
        with self._notice_lock:
            if cancel is not None and self._noticing is cancel:
                self._noticing = None
                motion = self.body.motion
                if not cancel.is_set() and motion.mode == "searching":
                    motion.set_mode("idle")

    def interrupt_noticing(self) -> None:
        with self._notice_lock:
            cancel, self._noticing = self._noticing, None
            if cancel is not None and not cancel.is_set():
                cancel.set()
                if self.body.motion.mode == "searching":  # the clip's stillness: no search runs outside a turn
                    self.body.motion.set_mode("idle")

    def noticed(self, seen: dict) -> None:
        """V-JEPA 2 saw a watched thing put down or picked up (memory/notice.py): the TV says so, and a new place gets
        its words. Andy says nothing: a notice, not an interruption."""
        names = _join(seen["things"])
        if seen["kind"] == "put":
            for label, mask in seen.get("masks", {}).items():
                self._note_place(label, seen["frame"], mask)
            self.screen.notice(self._tv(f"Noticed: {names}, put down", f"Visto: {names}, dejado"))
        else:
            self.screen.notice(self._tv(f"Noticed: {names}, picked up", f"Visto: {names}, recogido"))
        seen.pop("frame", None)
        self.chime("noticed")
        self.screen.used("V-JEPA 2 (noticing)", "device")
        self.refresh_panels()

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
        told = self._told_first(thing)
        if told:
            return told
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
            metres = self.places.metres(label) if last else None
            out.append({"label": label, "yaw": last[0], "pitch": last[1], "ago_s": round(self.clock() - at),
                        **({"metres": metres} if metres is not None else {})} if last else {"label": label})
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
            self.interrupt_noticing()
            # Andy speaks first here, so it says it's an AI when that's due, as at the start of any conversation
            self.reminders.deliver(r, (lambda: True) if self.quiet() else self._find_person,
                                   lambda words: (self.chime("reminder", even_when_quiet=True),
                                                  self.say(self.disclosure.prefix() + words)), now)
        if self.filming:  # a take mustn't be interrupted: only reminders (asked for) come
            self.refresh_panels()
            return
        if not self.quiet() and self.places.watching() and now - self._last_glance >= GLANCE_EVERY_S:
            self._last_glance = now
            self.interrupt_noticing()
            self.gesture("searching")
            self.screen.doing("Working", "Glancing around the room")
            try:
                glance(self.body, self.segmenter, self.places, on_seen=self._note_place)
            finally:
                self.gesture("idle")
                self.screen.doing("Waiting")
        today = _now(self.clock)
        if (self.places.homes() and not self.quiet() and today.hour == HOME_CHECK_HOUR
                and self._home_checked != today.date()):
            self._home_checked = today.date()
            self.interrupt_noticing()
            self.say(self.disclosure.prefix() + f"It's {HOME_CHECK_HOUR - 12} o'clock: let me check your things are home.")
            self.say(self.home_check(evening=True))
        if not self.quiet() and now - self._last_lost_look >= LOOK_EVERY_S and self.lost.looking():
            self._last_lost_look = now
            self._look_again()
        self.refresh_panels()

    def _look_again(self) -> str | None:
        """Lost and found (memory/lost.py): one look around for everything a search missed; a thing spotted gets the
        full search (it checks, points and measures), and if that finds it, Andy says so. What it said, or None."""
        lost = self.lost.looking()
        self.interrupt_noticing()
        self.gesture("searching")
        self.screen.doing("Working", "Looking again for " + _join(lost))
        try:
            spotted = spot(self.body, self.segmenter, lost)
        finally:
            self.gesture("idle")
            self.screen.doing("Waiting")
        self.lost.looked(lost)
        for thing in [t for t in lost if t in spotted]:
            since = self.lost.since(thing)
            self.finder.last_found, self._background = None, True
            try:
                self.find(thing, f"where is my {thing}")  # it checks, points and measures; the words are said below
            finally:
                self._background = False
            f = self.finder.last_found
            if f is None:
                continue  # a glimpse the search didn't confirm: keep looking, and say nothing
            where = (f"{f.for_you['words']}, at your {f.for_you['clock']} o'clock" if f.for_you else
                     side(f.yaw) + (f", {how_far(f.metres, metric=self.language != 'en')}" if f.metres is not None else ""))
            its = "They're" if _it(thing) == "them" else "It's"
            said = (f"Good news: your {thing} turned up! {its} {where}."
                    + (f" I'd been looking out for {_it(thing)} since {spoken_time(since)}." if since else ""))
            self._source, self._reason = "device", "Andy kept looking: SAM 3.1 spotted it, and the search confirmed it"
            self.screen.turned_up(said)
            self.say(self.disclosure.prefix() + said)
            return said
        return None

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


# "place 1" is the tools' own numbering, never something to say out loud ("I found a mug at place 1")
PLACE_NUMBERS = re.compile(r"\s*\(?\b(?:at |in |from )?places? \d+(?:\s*(?:,|and|or)\s*\d+)*\)?(?=[\s,.!?]|$)", re.I)
CLAUSES = re.compile(r"[,;.?!]+\s*(?:and\s+(?:then\s+)?|then\s+|also\s+)?|\s+and\s+(?:then\s+)?|\s+then\s+", re.I)


def _n(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def _methods(obj, stage: str, model: str) -> dict:
    """Every public method of obj, timed as this stage under the hood."""
    return {} if obj is None else {n: (stage, model) for n in dir(obj) if not n.startswith("_") and callable(getattr(obj, n, None))}


def _lives(thing: str) -> str:
    """"it lives" or "they live"."""
    return "they live" if _it(thing) == "them" else "it lives"


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


THANKS = re.compile(r"\b(thank you|thanks|thank u)\b", re.I)
HELLO = re.compile(r"^\W*(andy\W+)?(good morning|good afternoon|good evening|hello|hi there)\b", re.I)

FOUND_OPENERS = {"it": ("There it is!", "Found it!", "Ah, there it is!"),
                 "them": ("There they are!", "Found them!", "Ah, there they are!")}


ROOM_VIEWS = (-80.0, -40.0, 0.0, 40.0, 80.0)  # overlapping: the camera sees about 84 degrees across
ROOM_PITCH = 15.0
ROOM_THINGS = ("keys", "glasses", "cup", "phone", "remote", "watch", "wallet", "keyboard", "laptop", "chair")


def room_things(seen: list[dict], within_m: float = 0.2) -> list[dict]:
    """One entry per thing: the same label within 20 cm in several views is one thing. A thing seen in only one view
    counts only when SAM 3.1 was sure (a keyboard's edge read once as "keys", on the robot)."""
    groups: list[list[dict]] = []
    for t in sorted(seen, key=lambda t: -(t.get("score") or 0.0)):
        g = next((g for g in groups if g[0]["label"] == t["label"] and math.dist(g[0]["point"], t["point"]) <= within_m), None)
        (g.append(t) if g else groups.append([t]))
    out = []
    for g in groups:
        if len(g) < 2 and (g[0].get("score") or 0.0) < 0.85:
            continue
        x, y, z = (sum(t["point"][i] for t in g) / len(g) for i in range(3))
        out.append({"label": g[0]["label"], "point": [round(x, 3), round(y, 3), round(z, 3)],
                    "metres": round(math.sqrt(x * x + y * y + z * z), 2), "views": len(g),
                    "yaw": round(math.degrees(math.atan2(-x, z)), 1), "pitch": round(math.degrees(math.atan2(y, math.hypot(x, z))), 1)})
    return sorted(out, key=lambda t: t["metres"])


def millimetres(points_f16: bytes) -> bytes:
    """MapAnything's float16 metres as int16 millimetres, for the TV page (no half floats in its JavaScript)."""
    n = len(points_f16) // 2
    return struct.pack(f"<{n}h", *(max(-32000, min(32000, round(v * 1000))) for v in struct.unpack(f"<{n}e", points_f16)))


TOLD_AGAIN_S = 3 * 60  # asked again this soon after an answer from what was told: look around the room instead
HOME_CHECK_HOUR = 21  # each evening, Andy checks every thing with a home is there (9 pm)
RINGS = {"phone", "cell phone", "cellphone", "mobile", "mobile phone", "smartphone", "iphone", "tablet", "ipad"}
BEEPS = {"keys", "key", "wallet", "remote", "bag", "purse"}  # often on a tracker that plays a sound
HEARD_WITHIN_DEG = 35.0  # by its sound: a thing further than this from where it rang isn't the one ringing
GUIDE_AFTER_S = 5 * 60  # "help me reach it" means the thing found this long ago at most
SETUP_WAIT_S = 5 * 60  # the setup waits this long for an answer, then steps aside
SKIP = re.compile(r"^\W*(?:andy\W+)?(?:skip(?: it| that)?|not now|later|stop(?: the setup)?|cancel|never ?mind|no thanks?)\W*$", re.I)
COMMON_THINGS = ("reading glasses", "sunglasses", "glasses", "keys", "phone", "remote", "wallet", "purse", "watch", "mug",
                 "cup", "hearing aid", "pills", "book", "bag", "charger", "headphones", "umbrella")


def things_in(text: str) -> list[str]:
    """The everyday things named in an answer ("my keys and my reading glasses"), each once, longest name first."""
    found, rest = [], " " + text.lower() + " "
    for name in COMMON_THINGS:
        if re.search(rf"\b{name}s?\b", rest):
            found.append(name)
            rest = re.sub(rf"\b{name}s?\b", " ", rest)
    order = {name: text.lower().find(name.split()[0]) for name in found}
    return sorted(found, key=lambda n: order[n])


def _it(thing: str) -> str:
    return "them" if thing.endswith("s") and not thing.endswith("ss") else "it"
