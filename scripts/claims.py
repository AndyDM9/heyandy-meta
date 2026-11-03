"""Every figure the submission and the system card state, read from where it comes from.

A figure is something measured or set: "250 of 253", "1.1 degrees", "7.8 s", "9%". Each one the documents state is
listed here with its source: a scorecard's file in evals/results/ (read, and the words made from it here, from its
latest run unless the sentence names an earlier one), a value in the code (read from it), or, for a one-off
measurement, the section of docs/research.md that records it (which must say the same). Checked: the submission, the
system card, and the README down to its "Proof" section (with its badges) and its "Built during the event" section;
the README's long tables further down are made from the same files but not yet checked figure by figure. tests/test_claims.py fails when a document states a figure that isn't listed here, or
one its source no longer says: a new run that changes a number, a number edited by hand, or the best run quoted when
the latest says otherwise (the first check found that: "16.5 s" for the fall shot was the fastest of four rehearsals).

    uv run python scripts/claims.py          # each figure, where it comes from, and whether they agree
"""
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))  # the code, for values it sets

from results_index import RESULTS, files_for, latest  # noqa: E402

DOCS = ("docs/submission.md", "docs/system-card.md", "README.md")
README_UNTIL = "## Proof"  # the README is checked down to here, and this section too:
README_ALSO = ("## Built during the event",)
# what a measured figure looks like in prose: "N of M", "N times in M", and a number with degrees, seconds or a percent
NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"  # 1,000 is one number; "72," is 72 and a comma
FIGURE = re.compile(rf"\b{NUMBER}(?: of {NUMBER}| times in {NUMBER}| degrees|\s?°| s\b|%)")


def plain(text: str) -> str:
    """Prose as it reads: no bold or italics, no HTML or link targets (a badge's address, an image's width), one space
    between words (a figure may break across lines)."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\]\([^)\s]*\)", "]", text)
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def badges(text: str) -> str:
    """What each shields.io badge says ("On the robot 250 of 253 pointed"): read as prose too."""
    from urllib.parse import unquote

    out = []
    for m in re.finditer(r"img\.shields\.io/badge/([^\s\"?]+)", re.sub(r"<!--.*?-->", " ", text, flags=re.S)):
        parts = re.split(r"(?<!-)-(?!-)", m.group(1))[:-1]  # label-message-colour; "--" is a dash
        out.append(unquote(" ".join(parts)).replace("--", "-").replace("_", " "))
    return " · ".join(out)


def checked(name: str, text: str) -> str:
    """The part of a document that's checked: all of it, or for the README its top and the sections named above."""
    if name != "README.md":
        return text
    top = text.split(README_UNTIL)[0]
    also = [m.group(0) for h in README_ALSO for m in re.finditer(rf"(?ms)^{re.escape(h)}.*?(?=^## |\Z)", text)]
    return "\n".join([top, *also, badges(text)])


def _load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def summary(name: str) -> dict:
    return _load(name)["summary"]


def newest(stem: str) -> str:
    """A scorecard's latest run, the one a figure reads unless its sentence names another."""
    return latest(files_for(stem), stem)


def of(pair: str) -> tuple[int, int]:
    """'7/7', '7 of 7' or '0 / 0' as two numbers."""
    a, b = re.split(r"\s*(?:/|of)\s*", pair.strip())
    return int(a), int(b)


@dataclass(frozen=True)
class Figure:
    says: str                             # as the documents write it (plain)
    source: str                           # a file in evals/results/, a family of them, or "research.md §N"
    reads: Callable[[], str] | None = None  # the same words made from the file; None: the research section must say `quote`
    quote: str | tuple = ""                  # what research.md says (each of them, if several)


# ---- made from the files -------------------------------------------------------------------------------------------

def unattended_since_fix() -> str:
    after = [summary(f) for f in files_for("unattended") if re.search(r"\d{8}", f) and f > "unattended-20261030-1714.json"]
    return f"{sum(s['pointed'] for s in after)} of {sum(s['trials'] for s in after)} unattended searches"


def final_code() -> dict:
    return summary("unattended-20261101-2300.json")  # the final code: focus held, the true ray, the head read back


def emergency_runs() -> list[float]:
    """The fall shot in every dress rehearsal that had it, when Andy pointed at the phone."""
    out = []
    for f in sorted(glob.glob(str(RESULTS / "rehearsal-2*.json"))):
        for shot in _load(os.path.basename(f))["shots"]:
            if "emergency" in shot["shot"] and shot["ok"] and shot.get("pointed"):
                out.append(shot["seconds"])
    return out


def notes(name: str) -> tuple[int, int]:
    s = summary(name)
    sets = [v["followed"] for k, v in s.items() if k in ("first", "held out", "held out, second", "held out, third")]
    return sum(of(x)[0] for x in sets), sum(of(x)[1] for x in sets)


def sim(name: str, kind: str) -> dict:
    return summary(name)[kind]


def rehearsal_find() -> str:
    """The uncut find and the offline one, from the newest full dress rehearsal in which both pointed: a search that
    didn't find the thing isn't a find's time (November 3's keys, not seen where they lay, 32.3 s)."""
    for f in sorted(glob.glob(str(RESULTS / "rehearsal-2*.json")), reverse=True):
        shots = {s["shot"]: s for s in _load(os.path.basename(f))["shots"]}
        a, b = shots.get("the uncut find"), shots.get("the network unplugged")
        if a and b and a.get("pointed") and b.get("pointed"):
            t = sorted([a["seconds"], b["seconds"]])
            return f"from the words to Andy's spoken answer, {t[0]} to {t[1]} s (the dress rehearsal)"
    return "no dress rehearsal with both finds"


def later_signs() -> str:
    """Glimmer's second look on warning signs written after its wording was chosen, each asked as written and as heard."""
    yes, of = summary(newest("second-look"))["now"]["warning signs written afterwards"].split("/")
    n = {24: "twelve"}.get(int(of), str(int(of) // 2))
    return f"{yes} of {of} ({n} written after it, each as written and as heard)"


def crisis() -> dict:
    return summary(newest("crisis-languages"))


def everyday_crisis() -> tuple[int, int]:
    s = crisis()
    everyday = s["everyday requests"]
    taken = int(s["everyday taken for a crisis, before / now"].split("/")[-1])
    trick_taken, trick = of(s["everyday remarks built to trick it, taken for a crisis (now)"])
    return taken + trick_taken, everyday + trick


def no_advice_held_out() -> str:
    s = summary(newest("no-advice-second"))
    rest = "none of the rest judged advice" if s["advice given, now (judged)"] == 0 else f"{s['advice given, now (judged)']} of the rest judged advice"
    own = s["answered by Andy's own words"]
    return (f"held out: {own} of {s['questions']} caught by the rule, {rest}; "
            f"{s['everyday given the health line (must be 0)']} of {s['everyday requests']} everyday requests caught")


def physical() -> dict:
    return summary(newest("physical-fixed"))


def eyes() -> str:
    s = summary(newest("eyes"))
    wrong = "never a wrong one" if s["found, but wrong"] == 0 else f"{s['found, but wrong']} wrong"
    absent = "never \"found\" when it wasn't there" if s["said found"] == 0 else f"\"found\" {s['said found']} times when it wasn't there"
    return f"found {s['found, and right']} of {s['tables with it']}, {wrong}, {absent}"


def privacy() -> dict:
    return summary("privacy-audit.json")


def voice() -> str:
    d = _load("voice-clarity-20261030.json")
    mms = d["mms_tts"]["word_error"].values()
    return (f"{round(d['seamless_m4t_v2']['word_error'] * 100)}% of words misheard by a speech recogniser, against "
            f"{round(min(mms) * 100)} to {round(max(mms) * 100)}% for MMS-TTS")


def room() -> str:
    s = summary(newest("room"))
    across = max(v["yaw_spread_deg"] for v in s["across_scans"].values())
    return f"a median {s['within_scan_yaw_spread_median']} degrees, and scan to scan within {across:g}"


def agents() -> tuple[dict, dict]:
    return summary("agent-spark.json"), summary("agent-glimmer.json")


def both_agents() -> str:
    a, b = agents()
    if (a["right"], a["requests"]) != (b["right"], b["requests"]):
        return f"Muse Spark {a['right']} of {a['requests']}, Glimmer {b['right']} of {b['requests']}"
    return f"{a['right']} of {a['requests']} multi-part requests"


def languages() -> dict:
    return summary(newest("languages"))


def flagged() -> str:
    return summary(newest("guard-replies"))["Andy's real answers flagged"]


def hood() -> dict:
    return _load(newest("hood"))["latest"]


def live_strip() -> str:
    """The TV's "Meta, live" strip, read on the robot: each model's time when it first finished."""
    took = {}
    for seen in _load(newest("live-calls"))["seen"]:
        for part in seen["strip"].split("; "):
            if not part.startswith("*"):
                name, t = part.rsplit(" ", 2)[0], part.rsplit(" ", 2)[1]
                took.setdefault(name, t)
    return (f"SAM 3.1 seeing {took['SAM 3.1 seeing']} s · Muse Glimmer checking the picture "
            f"{took['Muse Glimmer checking the picture']} s · MapAnything how far {took['MapAnything how far']} s")


def code_value(where: str, name: str):
    """A value as the code sets it: a dataclass field's or a keyword's default."""
    import importlib
    import inspect

    module, _, attr = where.rpartition(".")
    obj = getattr(importlib.import_module(module), attr)
    if "." in name:
        func, name = name.split(".")
        return inspect.signature(getattr(obj, func)).parameters[name].default
    return obj.__dataclass_fields__[name].default


def gpu() -> dict:
    return summary(newest("gpu-budget"))


def power() -> dict:
    return summary(newest("energy"))


def breath() -> dict:
    night = next(v for k, v in summary(newest("ego-noise")).items() if k.startswith("night"))
    return {"an hour": f"{night['an hour']:,}", "z": f"{night['with the breath (twice a breath)']['z']:,.0f}",
            "other": night["control"]["largest z at any other rate"], "kept": night["keeps time with the breath"]}


def gaps() -> dict:
    return summary(newest("speech-gaps"))


def a11y() -> dict:
    return summary(newest("accessibility"))


def quiet_conversation() -> tuple[int, int]:
    c = summary(newest("room-talk"))["a conversation with Andy in a quiet room, now"]
    return c["answered without the name"], c["follow-ups said"]


def code_constant(module: str, name: str):
    import importlib

    return getattr(importlib.import_module(module), name)


def sound() -> str:
    d = _load(newest("sound"))
    return (f"{d['ringings_faced']} of {d['of']} ringings faced, within {max(d['spread_deg'].values()):.0f} degrees; "
            f"a voice {'never' if not d['voice_taken_for_a_ringing'] else 'taken for one'}")


def eyes_live() -> str:
    s = summary(newest("eyes-live"))
    t = s["seconds to 'There's your cup'"]
    both = "both sweeps" if s["found it"] == s["sweeps with our cup"] == 2 else f"{s['found it']} of {s['sweeps with our cup']} sweeps"
    return f"found in {both}, at {' and '.join(f'{x:.0f}' for x in t)} s"


FIGURES = [
    # finding, on the robot
    Figure("250 of 253 unattended searches", "unattended-* since the aim fix", unattended_since_fix),
    Figure("the final code a median 1.1 degrees off, 2.2 at worst", "unattended-20261101-2300",
           lambda: f"the final code a median {final_code()['aim_deg_median']} degrees off, {final_code()['aim_deg_worst']} at worst"),
    Figure("7.8 s a find", "unattended-20261101-2300", lambda: f"{final_code()['seconds_median']} s a find"),
    Figure("over 18 searches, a median 1.1 degrees and 2.2 at worst", "unattended-20261101-2300",
           lambda: f"over {final_code()['trials']} searches, a median {final_code()['aim_deg_median']} degrees and "
                   f"{final_code()['aim_deg_worst']} at worst"),
    Figure("a median 1.1 degrees off", "unattended-20261101-2300",
           lambda: f"a median {final_code()['aim_deg_median']} degrees off"),
    Figure("58.5% of pick-and-drop tasks", "research.md §85 (Liu et al., 2024)", quote="58.5% of pick-and-drop tasks in ten homes"),
    Figure("worst point 13.7 degrees off the middle of the view before", "unattended-20261031-0900 (before the fix)",
           lambda: f"worst point {summary('unattended-20261031-0900.json')['aim_deg_worst']} degrees off the middle of the view before"),
    Figure("13 of 15 right", "physical-fixed (judged by a person)",
           lambda: f"{physical()['correct'] + physical()['absent_correct']} of {physical()['trials']} right"),
    Figure("pointed at the thing 10 of 12 times, a median 2.5 degrees off; hidden, \"not found\" 3 of 3; never a wrong point",
           "physical-fixed (judged by a person)",
           lambda: (f"pointed at the thing {physical()['correct']} of {physical()['present']} times, a median "
                    f"{physical()['aim_deg_median']} degrees off; hidden, \"not found\" {physical()['absent_correct']} of "
                    f"{physical()['trials'] - physical()['present']}; "
                    + ("never a wrong point" if physical()["false_finds"] == 0 else f"{physical()['false_finds']} wrong points"))),
    Figure("16.5 to 27.1 s on the robot, over five dress rehearsals", "rehearsal-* (the fall shot, pointed)",
           lambda: f"{min(emergency_runs())} to {max(emergency_runs())} s on the robot, over "
                   f"{['no', 'one', 'two', 'three', 'four', 'five', 'six'][len(emergency_runs())]} dress rehearsals"),
    Figure("from the words to Andy's spoken answer, 10.9 to 11.6 s (the dress rehearsal)",
           "rehearsal (the newest with both finds pointed)", rehearsal_find),
    Figure("a median 0.9 degrees, and scan to scan within 1", "room (latest)", room),
    Figure("1.3 times too wide", "research.md §33", quote="1.3 times too wide"),
    Figure("9.6 s sooner", "research.md §50", quote="The answer comes about 9.6 s sooner"),
    # simulated search and the agents
    Figure("pointed at the wrong one 20 times in 100", "sim-fixed",
           lambda: f"pointed at the wrong one {sim('sim-fixed.json', 'described')['false_finds']} times in {sim('sim-fixed.json', 'described')['trials']}"),
    Figure("Glimmer's plan 18 of 20, 2 wrong", "sim-glimmer",
           lambda: "Glimmer's plan {correct} of {trials}, {false_finds} wrong".format(**sim("sim-glimmer.json", "described"))),
    Figure("Muse Spark 18 of 20, 2 wrong", "sim-spark",
           lambda: "Muse Spark {correct} of {trials}, {false_finds} wrong".format(**sim("sim-spark.json", "described"))),
    Figure("Glimmer 20 of 20 in 4.6 looks", "sim-glimmer",
           lambda: "Glimmer {correct} of {trials} in {looks_mean} looks".format(**sim("sim-glimmer.json", "behind"))),
    Figure("fixed sweep 92 of 100 in 7.1", "sim-fixed",
           lambda: "fixed sweep {correct} of {trials} in {looks_mean}".format(**sim("sim-fixed.json", "behind"))),
    Figure("Muse Spark 12 of 12, Glimmer offline 12 of 12", "agent-spark, agent-glimmer",
           lambda: "Muse Spark {0[right]} of {0[requests]}, Glimmer offline {1[right]} of {1[requests]}".format(*agents())),
    Figure("12 of 12 multi-part requests", "agent-spark and agent-glimmer, the same",
           both_agents),
    # privacy
    Figure("a day of 21 requests", "privacy-audit", lambda: f"a day of {privacy()['turns']} requests"),
    Figure("no camera picture reached the cloud (24 taken)", "privacy-audit",
           lambda: ("no camera picture" if privacy()["camera_pictures_to_cloud"] == 0 else f"{privacy()['camera_pictures_to_cloud']} camera pictures")
           + f" reached the cloud ({privacy()['camera_pictures_taken']} taken)"),
    Figure("0 of 24 camera pictures reached the cloud", "privacy-audit",
           lambda: f"{privacy()['camera_pictures_to_cloud']} of {privacy()['camera_pictures_taken']} camera pictures reached the cloud"),
    Figure("every word sent was on its turn's receipt", "privacy-audit",
           lambda: "every word sent was on its turn's receipt" if not privacy()["words_not_on_receipt"] else "words NOT on a receipt"),
    Figure("every word sent was on its receipt", "privacy-audit",
           lambda: "every word sent was on its receipt" if not privacy()["words_not_on_receipt"] else "words NOT on a receipt"),
    Figure("crisis words reached no model", "privacy-audit",
           lambda: "crisis words reached no model" if not privacy()["crisis_words_to"] else "crisis words reached a model"),
    # languages
    Figure("Spanish 41 of 41", "spanish-written", lambda: "Spanish {right} of {requests}".format(**summary("spanish-written.json"))),
    Figure("thirteen more 104 of 104", "languages (latest)",
           lambda: f"thirteen more {languages()['written right']} of {languages()['requests']}"),
    Figure("36 of 41 and 89 of 104", "spanish-spoken, languages (latest)",
           lambda: f"{summary('spanish-spoken.json')['right']} of {summary('spanish-spoken.json')['requests']} and "
                   f"{languages()['spoken right']} of {languages()['requests']}"),
    Figure("104 of 104 written requests in thirteen more languages reach the right ability, 89 of 104 spoken",
           "languages (latest)",
           lambda: (f"{languages()['written right']} of {languages()['requests']} written requests in thirteen more "
                    f"languages reach the right ability, {languages()['spoken right']} of {languages()['requests']} spoken")),
    Figure("Andy switched 31 times in 42, never wrongly", "hear-language (latest)",
           lambda: "Andy switched {0} times in {1}, {2}".format(
               summary(newest("hear-language"))["switched to the right language"],
               summary(newest("hear-language"))["requests in other languages"],
               "never wrongly" if summary(newest("hear-language"))["switched to a wrong language"] == 0 else "sometimes wrongly")),
    # in the browser
    Figure("7 of 7 fresh clips", "say-it (latest)",
           lambda: "{} of {} fresh clips".format(*of(summary(newest("say-it"))["fresh, the right scene"]))),
    Figure("found 20 of 24, never a wrong one, never \"found\" when it wasn't there", "eyes (latest)", eyes),
    # safety
    Figure("held out: 25 of 34 caught by the rule, none of the rest judged advice; 0 of 116 everyday requests caught",
           "no-advice-second (latest)", no_advice_held_out),
    Figure("Andy's real answers flagged 0 of 168", "guard-replies (latest)",
           lambda: f"Andy's real answers flagged {flagged()}"),
    Figure("60 of 60 indirect phrasings", "crisis-languages (latest)",
           lambda: f"{crisis()['caught now (and Llama Guard on the translation)']} of {crisis()['indirect phrasings']} indirect phrasings"),
    Figure("none of 144 everyday requests and trick remarks taken for one", "crisis-languages (latest)",
           lambda: "{} of {} everyday requests and trick remarks taken for one".format(
               "none" if everyday_crisis()[0] == 0 else everyday_crisis()[0], everyday_crisis()[1])),
    Figure("0 of 144 everyday or trick remarks taken for one", "crisis-languages (latest)",
           lambda: "{} of {} everyday or trick remarks taken for one".format(*everyday_crisis())),
    Figure("said in ways no list has, 42 of 45", "crisis-languages (latest): the second held-out set",
           lambda: "said in ways no list has, {} of {}".format(*of(crisis()["second held-out set (used for nothing)"]))),
    Figure("said in ways no list has: 42 of 45", "crisis-languages (latest): the second held-out set",
           lambda: "said in ways no list has: {} of {}".format(*of(crisis()["second held-out set (used for nothing)"]))),
    Figure("20 of 24 (twelve written after it, each as written and as heard)", "second-look (latest)", later_signs),
    Figure("9 of 54 notes got through, now 0 of 72", "notes-in-view-20261102-0920 (before), notes-in-view (latest)",
           lambda: "{} of {} notes got through, now {} of {}".format(*notes("notes-in-view-20261102-0920.json"), *notes(newest("notes-in-view")))),
    Figure("9 of 54 drawn notes got through before, 0 of 72 after", "notes-in-view-20261102-0920 (before), notes-in-view (latest)",
           lambda: "{} of {} drawn notes got through before, {} of {} after".format(*notes("notes-in-view-20261102-0920.json"), *notes(newest("notes-in-view")))),
    # the voice, and knowing the person's own things
    Figure("9% of words misheard by a speech recogniser, against 23 to 28% for MMS-TTS", "voice-clarity-20261030", voice),
    Figure("0.94 alike", "research.md §19", quote="scored 0.94 alike"),
    Figure("the right cup 3 of 5", "research.md §29", quote="Synthetic shuffles at batch 2: 3 of 5 right"),
    # the README's top: its badge, and the fall shot
    Figure("250 of 253 pointed", "unattended-* since the aim fix (the README's badge)",
           lambda: unattended_since_fix().replace("unattended searches", "pointed")),
    Figure("16.5 to 27.1 s from the words", "rehearsal-* (the fall shot, pointed)",
           lambda: f"{min(emergency_runs())} to {max(emergency_runs())} s from the words"),
    # the README: what Andy does
    Figure("250 of 253 searches on the robot", "unattended-* since the aim fix",
           lambda: unattended_since_fix().replace("unattended searches", "searches on the robot")),
    Figure("on the final code, 18 searches: a median 7.8 s and 1.1 degrees", "unattended-20261101-2300",
           lambda: f"on the final code, {final_code()['trials']} searches: a median {final_code()['seconds_median']} s and "
                   f"{final_code()['aim_deg_median']} degrees"),
    Figure("6 of 6 ringings faced, within 20 degrees; a voice never", "sound (latest)", sound),
    Figure("a \"lost\" watch found later, 4.1 degrees off", "lost-20261031-1653 (the watch, and a wallet not there)",
           lambda: "a \"lost\" {label} found later, {aim_deg} degrees off".format(**_load("lost-20261031-1653.json")["pointed_at"])),
    Figure("hearing (Omnilingual ASR) 0.13 s", "hood (latest)", lambda: f"hearing (Omnilingual ASR) {hood()['stages']['hear']} s"),
    Figure("12.8 s in all, the first sound at 0.13 s", "hood (latest)",
           lambda: f"{hood()['total']:.1f} s in all, the first sound at {hood()['first_sound']} s"),
    Figure("SAM 3.1 seeing 0.76 s · Muse Glimmer checking the picture 0.78 s · MapAnything how far 0.21 s", "live-calls (latest)",
           live_strip),
    Figure("after 20 s of quiet", "code: heyandy_meta.screen.hood.Hood.calls(keep_s)",
           lambda: f"after {code_value('heyandy_meta.screen.hood.Hood', 'calls.keep_s'):g} s of quiet"),
    Figure("the answer used to start 15.5 s after the words and now starts at 5.8 to 6.0 s; the whole turn went from 20.5 s "
           "to 10.7 to 11.0 s", "research.md §50",
           quote=("the answer at 15.5 s, done at 20.5 s", "the answer at 5.8 to 6.0 s, done at 10.7 to 11.0 s")),
    # the README: try it in your browser
    Figure("the right thing found 20 times in 24, never a wrong one; never \"found\" in 24 tables without it", "eyes (latest)",
           lambda: "the right thing found {} times in {}, never a wrong one; never \"found\" in {} tables without it".format(
               summary(newest("eyes"))["found, and right"], summary(newest("eyes"))["tables with it"],
               summary(newest("eyes"))["tables without it"]) if summary(newest("eyes"))["found, but wrong"] == 0
               == summary(newest("eyes"))["said found"] else "a wrong find, or one when it wasn't there"),
    Figure("only its flowers recoloured: 4 of 6", "eyes (latest)",
           lambda: "only its flowers recoloured: {} of {}".format(
               summary(newest("eyes"))["said found of the white cup's twin"],
               summary(newest("eyes"))["tables with the white cup's twin (only its painted flowers recoloured)"])),
    Figure("found in both sweeps, at 15 and 34 s", "eyes-live (latest)", eyes_live),
    Figure("the right scene 7 of 7", "say-it (latest)",
           lambda: "the right scene {} of {}".format(*of(summary(newest("say-it"))["fresh, the right scene"]))),
    Figure("the right one 31 times in 42, a wrong one never", "hear-language (latest)",
           lambda: "the right one {} times in {}, a wrong one {}".format(
               summary(newest("hear-language"))["switched to the right language"],
               summary(newest("hear-language"))["requests in other languages"],
               "never" if summary(newest("hear-language"))["switched to a wrong language"] == 0 else "sometimes")),
    # the README: why it's different
    Figure("(28 of 28 masks)", "research.md §32", quote="outlined every key of a keyboard (28 of 28 masks)"),
    Figure("a call 0.82 s to 0.30 s, a whole find 9.8 s to 7.8 s", "research.md §72",
           quote=("0.82 s a call -> 0.30", "7.8 s a find (9.8 before")),
    Figure("9 of 54 notes got through before, 0 of 72 after", "notes-in-view-20261102-0920 (before), notes-in-view (latest)",
           lambda: "{} of {} notes got through before, {} of {} after".format(*notes("notes-in-view-20261102-0920.json"), *notes(newest("notes-in-view")))),
    Figure("the right scene 15 of 24, then 21", "research.md §60",
           quote=("letter by letter", "the right scene 15 of 24. Snapping a near-miss word", "21. Through a microphone")),
    # the README: built during the event
    Figure("metric depth, about 0.2 s", "research.md §32", quote="0.2 s, about 3 GB"),
    Figure("from five looks, about 1 s", "research.md §33", quote=("five looks", "joined in 1.0 s")),
    Figure("correcting the aim past 3 degrees, at most twice", "code: heyandy_meta.finder.search.Finder",
           lambda: "correcting the aim past {:g} degrees, at most {}".format(
               code_value("heyandy_meta.finder.search.Finder", "aim_tolerance"),
               {1: "once", 2: "twice", 3: "three times"}[code_value("heyandy_meta.finder.search.Finder", "aim_corrections")])),
    Figure("slowed 8%", "voice-clarity-20261030 (the voice chosen)",
           lambda: re.search(r"slowed \d+%", _load("voice-clarity-20261030.json")["chosen"]).group(0)),
    # the system card: a conversation it isn't part of
    Figure("a real meeting near the robot, replayed: 37 answers became 4", "room-talk (latest)",
           lambda: "a real meeting near the robot, replayed: {} answers became {}".format(
               summary(newest("room-talk"))["replayed, the old rules"]["answered"],
               summary(newest("room-talk"))["replayed, now"]["answered"])),
    Figure("a quiet conversation keeps 6 of 8 follow-ups", "room-talk (latest)",
           lambda: "a quiet conversation keeps {} of {} follow-ups".format(*quiet_conversation())),
    Figure("at most six follow-ups in a row", "code: heyandy_meta.voice.loop.FOLLOW_UPS",
           lambda: f"at most {['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight'][code_constant('heyandy_meta.voice.loop', 'FOLLOW_UPS')]} follow-ups in a row"),
    # what it takes: GPU memory at rest
    Figure("Measured at rest: 40.5 GB, of which the language model (Muse Glimmer) is 17.6 GB", "gpu-budget (latest)",
           lambda: f"Measured at rest: {gpu()['total GB']} GB, of which the language model (Muse Glimmer) is "
                   f"{gpu()['language model GB']} GB"),
    Figure("(seeing, hearing, the voice, the guards, how far) 22.9 GB, one card's worth", "gpu-budget (latest)",
           lambda: f"(seeing, hearing, the voice, the guards, how far) {gpu()['everything else GB']} GB, "
                   + ("one card's worth" if gpu()["everything else fits one 24 GB card"] else "more than one card")),
    Figure("40.5 GB at rest, the language model 17.6 GB of it", "gpu-budget (latest)",
           lambda: f"{gpu()['total GB']} GB at rest, the language model {gpu()['language model GB']} GB of it"),
    # what it costs to keep, and the breath it heard
    Figure("the two cards drew 188.1 W ($24.92 a month at the U.S. average price)", "energy (latest)",
           lambda: f"the two cards drew {power()['all']['both cards']['watts']} W "
                   f"(${power()['all']['both cards']['dollars a month']} a month at the U.S. average price)"),
    Figure("the two cards drew 188.1 W over 29.8 hours with Andy running: 4.51 kWh a day, $24.92 a month",
           "energy (latest)",
           lambda: "the two cards drew {watts} W over {h} hours with Andy running: {kwh} kWh a day, ${usd} a month".format(
               watts=power()["all"]["both cards"]["watts"], h=power()["all"]["hours"],
               kwh=power()["all"]["both cards"]["kWh a day"], usd=power()["all"]["both cards"]["dollars a month"])),
    Figure("135.3 W through a night with no one talking to it, against 17.6 W resting", "energy (latest)",
           lambda: f"{power()['night (no turns)']['cards']['GPU 1']['average W']} W through a night with no one "
                   f"talking to it, against {power()['all']['cards']['GPU 1']['resting W (median)']} W resting"),
    Figure("overnight 1,043 sounds an hour kept time with it", "ego-noise (latest)",
           lambda: f"overnight {breath()['an hour']} sounds an hour kept time with it" if breath()["kept"]
           else "overnight the sounds didn't keep time with it"),
    Figure("Overnight Andy let go 1,043 sounds an hour", "ego-noise (latest)",
           lambda: f"Overnight Andy let go {breath()['an hour']} sounds an hour"),
    Figure("z 1,926 at its rate, 5.1 at most at any other", "ego-noise (latest)",
           lambda: f"z {breath()['z']} at its rate, {breath()['other']} at most at any other"),
    # silence inside its answers
    Figure("between its sentences, 0.56 s of silence became 0.05 s", "speech-gaps (latest)",
           lambda: "between its sentences, {} s of silence became {} s".format(
               gaps()["made as said (before)"]["silence between sentences, median s"],
               gaps()["made ahead (now)"]["silence between sentences, median s"])),
    Figure("14.6 s of silence in 8 answers became 1.0 s", "speech-gaps (latest)",
           lambda: "{} s of silence in {} answers became {} s".format(
               gaps()["made as said (before)"]["silence in all the answers s"], gaps()["made as said (before)"]["answers"],
               gaps()["made ahead (now)"]["silence in all the answers s"])),
    # the open weights, every file
    Figure("54 of 54 files", "open-weights-all (latest)",
           lambda: "{matched} of {files} files".format(**summary(newest("open-weights-all")))
           if summary(newest("open-weights-all"))["every file matches"] else "not every file matches"),
    Figure("538 of 538 lines Andy says, in fifteen languages", "voice-tokenizer (latest)",
           lambda: "{same} of {lines} lines Andy says, in {n} languages".format(
               same=summary(newest("voice-tokenizer"))["same tokens"], lines=summary(newest("voice-tokenizer"))["lines"],
               n={15: "fifteen"}.get(summary(newest("voice-tokenizer"))["languages"],
                                     summary(newest("voice-tokenizer"))["languages"]))),
    # the public demo, for people who see less well
    Figure("pass on all 68 of its states", "accessibility (latest)",
           lambda: f"pass on all {a11y()['pages and states']} of its states" if a11y()["with an axe violation"] == 0
           else f"fail on {a11y()['with an axe violation']} of {a11y()['pages and states']} states"),
    Figure("none of 1,572 texts measured from the pixels is below AA contrast", "accessibility (latest)",
           lambda: "{} of {:,} texts measured from the pixels is below AA contrast".format(
               "none" if a11y()["texts below WCAG AA contrast"] == 0 else a11y()["texts below WCAG AA contrast"],
               a11y()["texts measured from pixels"])),
    Figure("none of 1,572 texts is below AA contrast", "accessibility (latest)",
           lambda: "{} of {:,} texts is below AA contrast".format(
               "none" if a11y()["texts below WCAG AA contrast"] == 0 else a11y()["texts below WCAG AA contrast"],
               a11y()["texts measured from pixels"])),
    Figure("0 of 72 drawn notes got through", "notes-in-view (latest)",
           lambda: "{} of {} drawn notes got through".format(*notes(newest("notes-in-view")))),
]


def research_section(number: int) -> str:
    text = (ROOT / "docs" / "research.md").read_text()
    m = re.search(rf"^## {number}\. .*?(?=^## \d+\. |\Z)", text, re.S | re.M)
    return plain(m.group(0)) if m else ""


def disagreements() -> list[str]:
    """Each listed figure whose source no longer says it."""
    out = []
    for f in FIGURES:
        if f.reads is None:
            number = int(re.search(r"§(\d+)", f.source).group(1))
            for quote in (f.quote,) if isinstance(f.quote, str) else f.quote:
                if plain(quote) not in research_section(number):
                    out.append(f"\"{f.says}\": research.md §{number} doesn't say \"{quote}\"")
            continue
        try:
            made = f.reads()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError, ImportError, FileNotFoundError) as e:
            out.append(f"\"{f.says}\": couldn't read it from {f.source} ({type(e).__name__}: {e})")
            continue
        if made != f.says:
            out.append(f"\"{f.says}\": {f.source} now says \"{made}\"")
    return out


def unsourced(name: str, text: str) -> list[str]:
    """Each figure in a document that no listed figure covers."""
    prose = plain(text)
    covered = []
    for f in FIGURES:
        covered += [(m.start(), m.end()) for m in re.finditer(re.escape(f.says), prose)]
    out = []
    for m in FIGURE.finditer(prose):
        if not any(a <= m.start() and m.end() <= b for a, b in covered):
            out.append(f"{name}: \"{m.group(0)}\" in \"…{prose[max(0, m.start() - 50):m.end() + 20]}…\" has no source in scripts/claims.py")
    return out


def problems(docs=DOCS) -> list[str]:
    out = disagreements()
    for name in docs:
        out += unsourced(name, checked(name, (ROOT / name).read_text()))
    return out


def main() -> None:
    bad = set(disagreements())
    for f in FIGURES:
        flag = "DIFFERS" if any(b.startswith(f"\"{f.says}\"") for b in bad) else "ok"
        print(f"{flag:8} {f.says}\n         from {f.source}")
    rest = [p for name in DOCS for p in unsourced(name, checked(name, (ROOT / name).read_text()))]
    for p in [*bad, *rest]:
        print("PROBLEM", p)
    print(f"{len(FIGURES)} figures; {len(bad)} differ from their source; {len(rest)} stated without one")
    sys.exit(1 if bad or rest else 0)


if __name__ == "__main__":
    main()
