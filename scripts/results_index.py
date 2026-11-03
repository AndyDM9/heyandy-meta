"""evals/results/README.md: every scorecard, what it measures, its latest result read from the file, and the earlier
runs kept beside it (failures included), so anyone checking a claim lands on a readable page, not a list of files.

    uv run python scripts/results_index.py          # writes evals/results/README.md (a test checks it's current)
"""
import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def unattended(files: list[str]) -> str:
    after = [load(f)["summary"] for f in files if f > "unattended-20261030-1714.json"]  # after the aim fix
    trials, pointed = sum(s["trials"] for s in after), sum(s["pointed"] for s in after)
    last = load(files[-1])["summary"]
    return (f"**{pointed} of {trials}** searches ended in a point over {len(after)} runs since the aim fix; the latest run: "
            f"median {last['aim_deg_median']}° off the middle of the view, {last['seconds_median']} s")


def sim(f: str) -> str:
    s = load(f)["summary"]
    return " · ".join(f"{k} {v['correct']}/{v['trials']}" + (f" ({v['false_finds']} wrong)" if v["false_finds"] else "")
                      for k, v in s.items())


def agent(f: str) -> str:
    s = load(f)["summary"]
    return f"**{s['right']} of {s['requests']}** multi-part requests done right, median {s['seconds_median']} s"


def privacy(f: str) -> str:
    s = load(f)["summary"]
    return (f"**{s['turns_ok']} of {s['turns']}** turns pass; camera pictures to the cloud **{s['camera_pictures_to_cloud']}** of "
            f"{s['camera_pictures_taken']}; {s['turns_with_nothing_sent']} turns sent nothing")


def spanish(f: str) -> str:
    s = load(f)["summary"]
    return f"**{s['right']} of {s['requests']}** reach the right ability ({'spoken and heard' if s['spoken'] else 'written'})"


def languages(f: str) -> str:
    s = load(f)["summary"]
    return (f"{s['languages']} languages: **{s['written right']} of {s['requests']}** written, **{s['spoken right']}** spoken; "
            f"Andy's answers heard back, median {s['Andy heard back, median']}")


def hear(f: str) -> str:
    s = load(f)["summary"]
    return (f"switched to the right language **{s['switched to the right language']} of {s['requests in other languages']}**, "
            f"a wrong one {s['switched to a wrong language']}; English switched {s['english switched (must be 0)']} of {s['english said']}")


def crisis(f: str) -> str:
    s = load(f)["summary"]
    parts = [f"indirect phrasings **{s['caught now (and Llama Guard on the translation)']} of {s['indirect phrasings']}**"]
    for key in ("first held-out set (then used for the 988 warning signs)", "second held-out set (used for nothing)",
                "everyday taken for a crisis, before / now", "everyday remarks built to trick it, taken for a crisis (now)"):
        if key in s:
            parts.append(f"{key}: {s[key]}")
    return "; ".join(parts)


def physical(f: str) -> str:
    s = load(f)["summary"]
    absent = s["trials"] - s["present"]
    aim = s.get("aim_deg_median")
    return (f"out where it could be seen, pointed at the thing **{s['correct']} of {s['present']}** (judged by a person;"
            f" not found {s['missed']}, near but off {s['off']})"
            + (f"; hidden, said not found **{s['absent_correct']} of {absent}**" if absent else "")
            + f"; pointed at something else: {s['false_finds']}"
            + (f"; a median {aim}° off the middle of the view" if aim is not None else "")
            + f"; a median {s['seconds_median']} s")


def no_advice(f: str) -> str:
    s = load(f)["summary"]
    own = s["answered by Andy's own words"]
    return (f"{s['questions']} health questions in {s['in languages']} languages: **{own}** "
            f"answered by Andy's own words, **{s['advice given, now (judged)']}** with advice (before the rule: "
            f"{s['advice given, before the rule (judged)']}); everyday requests given the health line: "
            f"**{s['everyday given the health line (must be 0)']} of {s['everyday requests']}**")


def guard_replies(f: str) -> str:
    s = load(f)["summary"]
    flagged = s["Andy's real answers flagged"]
    return (f"advice heard in **{s['advice caught, held out']}** held-out advising answers ({s['advice caught, first set (chose the wording)']} "
            f"in the set that chose the wording); Andy's real answers flagged: **{flagged}**; "
            f"{s['seconds, median']} s")


def eyes(f: str) -> str:
    s = load(f)["summary"]
    return (f"found **{s['found, and right']} of {s['tables with it']}**, wrong {s['found, but wrong']}; "
            f"\"found\" without it {s['said found']} of {s['tables without it']}")


def eyes_live(f: str) -> str:
    s = load(f)["summary"]
    seconds = s["seconds to 'There's your cup'"]
    return (f"found in **{s['found it']} of {s['sweeps with our cup']}** sweeps ({seconds} s); "
            f"\"found\" without it {s['said found without it']}, in {s['frames']} frames, {s['seconds a frame, median']} s a frame")


def say_it(f: str) -> str:
    s = load(f)["summary"]
    return (f"fresh: the right scene **{s['fresh, the right scene']}**, nothing forced {s['fresh, nothing forced (no scene)']}; "
            f"tuning set {s['tuning set, the right scene']}; {s['seconds to hear, median']} s to hear")


def rehearsal(f: str) -> str:
    d = load(f)
    ok = sum(s["ok"] for s in d["shots"])
    missed = [s["shot"] for s in d["shots"] if not s["ok"]]
    return f"**{ok} of {len(d['shots'])}** storyboard shots worked" + (f"; to fix: {', '.join(missed)}" if missed else ": READY")


def room(f: str) -> str:
    s = load(f)["summary"]["across_scans"]
    return (f"scan to scan within **{max(v['yaw_spread_deg'] for v in s.values()):.1f}°** and "
            f"**{max(v['metres_spread'] for v in s.values()) * 100:.0f} cm**")


def lens(f: str) -> str:
    d = load(f)
    return (f"measured focal length **{d['focal_px']} px**: {d['fitted']['rms_deg']}° RMS, against "
            f"{d['published_1116']['rms_deg']}° for the published 1116 px ({d['samples']} sightings)")


def sound(f: str) -> str:
    d = load(f)
    return (f"**{d['ringings_faced']} of {d['of']}** ringings turned to, within {max(d['spread_deg'].values()):.0f}°; a voice "
            f"taken for one: {'yes' if d['voice_taken_for_a_ringing'] else 'never'}")


def lost(f: str) -> str:
    d = load(f)
    p = d.get("pointed_at") or {}
    return f"said, unprompted: \"{d['said'][:70]}...\"; pointed {p.get('aim_deg', '?')}° off" if d.get("said") else "nothing said"


def home(f: str) -> str:
    d = load(f)
    return f"\"{' '.join(d['check_said'])[:110]}...\", {d['check_seconds']} s"


def told(f: str) -> str:
    t = load(f)["turns"]
    return f"{len(t)} turns; asked first, answered with **{t[1].get('looks', '?')} looks**" if len(t) > 1 else "see the file"


def selfcheck(f: str) -> str:
    runs = load(f)["runs"]
    return " / ".join(f"{'all running' if not r['stopped'] else r['stopped'] + ' stopped'}: \"{r['said'][22:90]}...\"" for r in runs)


def hood(f: str) -> str:
    d = load(f)["latest"]
    return f"{d['what']}: **{d['total']} s** in all, the first sound at {d['first_sound']} s"


def guide(f: str) -> str:
    d = load(f)
    return f"{d['frames']} frames of an empty table, a hand made up in **{d['frames_with_a_hand']}**; {d['per_second']} frames a second"


def notice(f: str) -> str:
    s = load(f)["summary"]
    return f"{s['clips']} clips of an empty table: **{s['false_alarms']}** false alarms"


def filming(f: str) -> str:
    d = load(f)
    return f"**{d['heard']} of {d['of']}** claps heard on the robot"


def finder_ring(f: str) -> str:
    runs = load(f)["runs"]
    return f"{len(runs)} runs of \"Ring it\" on the robot ({load(f)['how'][:60]}...)"


def finder_finds(f: str) -> str:
    d = load(f)["summary"]
    return (f"{d['found']} of {d['asked']} found; {d['within_1_7']} of {d['checked']} points within 1.7 degrees by its own "
            f"camera, a median {d['aim_median']}; about {d['seconds_median_middle_view']} s when the middle view sees it")


def open_weights(f: str) -> str:
    d = load(f)
    return (f"{d['served file']} ({d['quantization']}) served on our GPU: sha256 {d['served sha256'][:12]}… "
            f"{'matches' if d['matches'] else 'does NOT match'} Meta's published weights ({d['repository']})")


def open_weights_all(f: str) -> str:
    d = load(f)
    s = d["summary"]
    return (f"**{s['matched']} of {s['files']}** files of the {s['models']} open-weight models Andy runs match what Meta "
            f"published, at the revision Andy loads (" + ", ".join(r["model"] for r in d["models"]) + ")")


def gpu_budget(f: str) -> str:
    s = load(f)["summary"]
    return (f"**{s['total GB']} GB** at rest on the two GPUs: the language model {s['language model GB']} GB, everything "
            f"else **{s['everything else GB']} GB**" + (" (one 24 GB card's worth)" if s["everything else fits one 24 GB card"] else ""))


def speech_gaps(f: str) -> str:
    s = load(f)["summary"]
    was, now = s["made as said (before)"], s["made ahead (now)"]
    return (f"silence between an answer's sentences: **{now['silence between sentences, median s']} s** (median; was "
            f"{was['silence between sentences, median s']} s, at worst {was['silence between sentences, longest s']}); "
            f"{was['silence in all the answers s']} s of silence in {was['answers']} answers became "
            f"{now['silence in all the answers s']} s; first sound {was['first sound, median s']} s became "
            f"{now['first sound, median s']} s")


def energy(f: str) -> str:
    s = load(f)["summary"]
    every, night = s["all"], s["night (no turns)"]
    return (f"the two GPUs drew **{every['both cards']['watts']} W** over {every['hours']} h with Andy running "
            f"({every['both cards']['kWh a day']} kWh a day, ${every['both cards']['dollars a month']} a month at the U.S. "
            f"average); through a night with no turns GPU 1 still drew {night['cards']['GPU 1']['average W']} W, against "
            f"{every['cards']['GPU 1']['resting W (median)']} W resting")


def ego_noise(f: str) -> str:
    s = load(f)["summary"]
    first = next(k for k in s if k.startswith("night"))  # the night before Andy rested; nights after it follow
    night, twice = s[first], s[first]["with the breath (twice a breath)"]
    after = {k: v for k, v in s.items() if k != first and not k.startswith("day")}
    line = (f"overnight, {night['an hour']:,} sounds an hour Andy let go kept time with its own breathing (z "
            f"{twice['z']:,.0f}; any other rate {night['control']['largest z at any other rate']} at most)")
    for k, v in after.items():
        line += (f"; {k}: {v['an hour']:,} an hour, " + ("still with the breath" if v["keeps time with the breath"]
                                                          else "no sign of the breath"))
    return line


def notes_in_view(f: str) -> str:
    d = load(f)["summary"]
    sets = [v for k, v in d.items() if k in ("first", "held out", "held out, second", "held out, third")]
    got = sum(int(v["followed"].split(" of ")[0]) for v in sets)
    of = sum(int(v["followed"].split(" of ")[1]) for v in sets)
    return (f"{got} of {of} notes that try to instruct Andy got through ({d.get('label') or 'as built'}); harmless notes: "
            f"the mug still said {d['harmless, the mug still said']}")


def room_talk(f: str) -> str:
    s = load(f)["summary"]
    old, now = s["replayed, the old rules"], s["replayed, now"]
    return (f"{s['minutes']} minutes of a meeting near the robot ({s['the robot answered (logged)']} answered then): replayed, "
            f"the old rules **{old['answered']}**, now **{now['answered']}** (at most {now['most in ten minutes']} in ten "
            f"minutes); a quiet conversation keeps {s['a conversation with Andy in a quiet room, now']['answered without the name']} "
            f"of {s['a conversation with Andy in a quiet room, now']['follow-ups said']} follow-ups")


def accessibility(f: str) -> str:
    s = load(f)["summary"]
    return (f"{s['pages and states']} page states (every scene, the story, its end card, Andy's eyes, under the hood; "
            f"desktop and phone): axe violations in **{s['with an axe violation']}**; {s['texts measured from pixels']} "
            f"texts' contrast measured from the pixels, **{s['texts below WCAG AA contrast']}** below AA")


def live_calls(f: str) -> str:
    return f"{len(load(f)['seen'])} moments of the TV's \"Meta, live\" strip during a search on the robot"


def voice(f: str) -> str:
    return load(f)["chosen"]


def smoke(f: str) -> str:
    d = load(f)
    return f"{len(d['steps'])} calls through the Model API, ${d['spent_usd']:.2f}"


# (title, what it measures, the scorecard's module, the files' name before the date or "-", headline)
CARDS = [
    ("On the robot", None, None, None, None),
    ("Unattended searches", "the real robot searching again and again for things always in the room: points, aim, time",
     "evals.unattended", "unattended", "unattended"),
    ("Physical scorecard", "a person puts each thing somewhere (or hides it) and judges where Andy points",
     "evals.physical", "physical", physical),
    ("Dress rehearsal", "each line of the video's storyboard as a whole spoken turn on the robot", "evals.rehearsal", "rehearsal", rehearsal),
    ("What it's told", "\"I'm putting my passport in the top drawer\", then \"where's my passport?\"", "evals.told", "told", told),
    ("Homes", "\"my keys live here\", then \"is everything home?\" with one thing away", "evals.home", "home", home),
    ("It doesn't give up", "a miss becomes a promise: found later, pointed at and said, unprompted", "evals.lost", "lost", lost),
    ("By its ring", "\"I'm ringing my phone\": Andy turns to a ringtone, never to a voice", "evals.sound", "sound", sound),
    ("Help me reach it", "the hand-guiding on an empty table: never a hand made up", "evals.guide", "guide", guide),
    ("Are you OK?", "Andy's check of itself, once with a service stopped on purpose", "evals.selfcheck", "selfcheck", selfcheck),
    ("Under the hood", "real turns timed stage by stage", "evals.hood", "hood", hood),
    ("Silence in its answers", "Andy's real voice service making each sentence of four answers, said in the turn's own "
     "order (checked, then the head turned), each made when said or made ahead as it arrives; a pretend speaker plays "
     "nothing", "evals.speech_gaps", "speech-gaps", speech_gaps),
    ("The room in 3D", "five looks joined by MapAnything, scan to scan", "evals.room", "room", room),
    ("Its own lens", "the focal length Andy measured with its own camera", "evals.lens", "lens", lens),
    ("Noticing", "V-JEPA 2 on clips of an empty table: nothing noticed", "evals.notice", "notice-empty", notice),
    ("Filming mode", "\"take one\": the clap heard in the robot's own sound", "evals.filming", "filming", filming),
    ("Andy Finder", "the Reachy Mini app's \"Ring it\", on the robot", "research.md section 47", "finder-ring", finder_ring),
    ("What it takes", "each service's GPU memory at rest between turns (nvidia-smi per process): the language model, "
     "and everything else", "scripts/gpu_budget.py", "gpu-budget", gpu_budget),
    ("What it costs", "each GPU's power from Andy's own once-a-second log, priced at the U.S. residential average (EIA)",
     "scripts/energy.py", "energy", energy),
    ("Hearing its own breath", "the times of the sounds Andy let go (never a sound or a word), against the 0.22-a-second "
     "breath of its head and antennas, and every other rate", "evals.ego_noise", "ego-noise", ego_noise),
    ("Open weights, every file", "each of the nine open-weight models' files on this computer against Meta's published "
     "hashes: Hugging Face's SHA-256 and git hashes at the pinned revision, Omnilingual ASR's against Meta's download server",
     "scripts/verify_all_weights.py", "open-weights-all", open_weights_all),
    ("Open weights, verified", "the Muse Glimmer file served on our own hardware, checked against Meta's published SHA-256",
     "scripts/verify_open_weights.py", "open-weights", open_weights),
    ("Notes in view", "a note left in view can't instruct Andy: drawn notes through its own picture checks, Muse Glimmer "
     "and Prompt Guard 2 on this computer", "evals.notes_in_view", "notes-in-view", notes_in_view),
    ("Andy Finder, finding", "the Reachy Mini app's finds on the robot, its point checked by its own camera",
     "research.md section 73", "andy-finder", finder_finds),
    ("A conversation it isn't part of", "a real meeting's timing (only when each utterance ended, and whether Andy answered) "
     "replayed through Andy's listening, the old rules and now", "evals.room_talk", "room-talk", room_talk),
    ("Meta's models, live", "the TV's strip of model calls, read during a search on the robot", "research.md section 51", "live-calls", live_calls),
    ("The voice, picked by ear", "five versions of Andy's voice played on the robot's speaker", "research.md section 32", "voice-clarity", voice),
    ("The Model API", "the first calls through Meta's Model API", "scripts/smoke_model_api.py", "smoke-model-api", smoke),
    ("Simulated, and the agents", None, None, None, None),
    ("Search, fixed sweep", "seeded rooms, the robot's camera model: in front / behind / beside a TV / absent / look-alikes",
     "evals.sim", "sim-fixed", sim),
    ("Search, Glimmer plans", "the same rooms, Muse Glimmer planning on this computer", "evals.sim --policy glimmer", "sim-glimmer", sim),
    ("Search, Muse Spark plans", "the same rooms, Muse Spark planning through the Model API", "evals.sim --policy spark", "sim-spark", sim),
    ("Agent, Muse Spark", "12 requests with several parts, scored on what the robot did", "evals.agent --brain spark", "agent-spark", agent),
    ("Agent, Glimmer offline", "the same, on this computer", "evals.agent --brain glimmer", "agent-glimmer", agent),
    ("Privacy and safety", None, None, None, None),
    ("Privacy audit", "a day of 21 requests, every outgoing request recorded", "evals.privacy", "privacy-audit", privacy),
    ("Privacy audit, offline", "the same day with the network off", "evals.privacy --offline", "privacy-audit-offline", privacy),
    ("Crisis check, 15 languages", "indirect phrasings, held-out warning signs, everyday remarks that must never count",
     "evals.crisis_languages", "crisis-languages", crisis),
    ("No health advice", "health questions, written after the rule, in all 15 languages: Andy's own words or a model's, "
     "and was it advice?", "evals.no_advice", "no-advice", no_advice),
    ("No health advice, held out", "a second set of questions, written before the first set's results and used for "
     "nothing", "evals.no_advice --set second", "no-advice-second", no_advice),
    ("Llama Guard 3 reads the answers", "answers that advise, and Andy's real answers, read as the Agent's turn for "
     "health advice", "evals.guard_replies", "guard-replies", guard_replies),
    ("Languages", None, None, None, None),
    ("Spanish, written", "41 requests, several ways of asking for each ability", "evals.spanish", "spanish-written", spanish),
    ("Spanish, spoken", "the same, said by Andy's voice and heard by Omnilingual ASR", "evals.spanish --spoken", "spanish-spoken", spanish),
    ("Thirteen more languages", "eight everyday requests in each, written and spoken", "evals.languages", "languages", languages),
    ("Noticing the language", "called in one of fourteen languages, does Andy switch to it?", "evals.hear_language", "hear-language", hear),
    ("In the browser", None, None, None, None),
    ("For people who see less well", "axe-core's WCAG 2.2 A and AA checks on the public demo, and text contrast measured "
     "from the pixels where axe can't decide it", "evals.accessibility", "accessibility", accessibility),
    ("Andy's eyes", "DINOv2 in the browser, museum photos: yours among look-alikes, and not there at all", "evals.eyes", "eyes", eyes),
    ("Andy's eyes, live", "sweeping a camera (a video of one) over our cup and its look-alikes", "evals.eyes_live", "eyes-live", eyes_live),
    ("Say it", "the demo's microphone: Meta's wav2vec 2.0 in the browser, phrases scored by CTC", "evals.say_it", "say-it", say_it),
]


def files_for(stem: str) -> list[str]:
    """The files of one scorecard: its dated runs and its named earlier runs (before-fixes, oct28, ...), not those of
    another scorecard whose name starts with this one's (privacy-audit-offline isn't privacy-audit's)."""
    longer = [c[3] for c in CARDS if c[3] and c[3] != stem and c[3].startswith(stem)]
    out = []
    for path in glob.glob(str(RESULTS / "*.json")):
        name = os.path.basename(path)
        base = re.sub(r"-?\d{8}(-\d{4})?", "", name).removesuffix(".json")
        if (base == stem or base.startswith(stem + "-")) and not any(base == x or base.startswith(x + "-") for x in longer):
            out.append(name)
    return sorted(out)


def latest(names: list[str], stem: str) -> str:
    """The scorecard's own latest: the plain file if it's rewritten in place (sim-glimmer.json), else its most recent
    date; named variants (sound-app, -before-fixes) are earlier runs."""
    own = [n for n in names if re.sub(r"-?\d{8}(-\d{4})?", "", n).removesuffix(".json") == stem]
    if f"{stem}.json" in own:
        return f"{stem}.json"
    date = lambda n: (re.search(r"\d{8}(-\d{4})?", n) or re.search("", n)).group(0)  # noqa: E731
    return max(own or names, key=date)


def cards() -> list[tuple[str, list[dict]]]:
    """Each section's scorecards, as data: title, what it measures, how to run it, its latest result (markdown, bold only),
    its file and the earlier runs kept beside it. The markdown page (build) and the Space's page (proof.html) read it."""
    out: list[tuple[str, list[dict]]] = []
    for title, what, module, stem, head in CARDS:
        if what is None:
            out.append((title, []))
            continue
        names = files_for(stem)
        if not names:
            continue
        main = latest(names, stem)
        try:
            text = unattended(sorted(n for n in names if re.search(r"\d{8}", n))) if head == "unattended" else head(main)
        except (KeyError, IndexError, TypeError, ValueError):
            text = "see the file"
        how = (f"a one-off run, {module}" if module.startswith("research") else f"uv run python {module}"
               if module.endswith(".py") else f"uv run python -m {module}")
        out[-1][1].append({"title": title, "what": what, "how": how, "result": text, "file": main,
                           "earlier": [n for n in names if n != main]})
    return out


def build() -> str:
    lines = ["# The scorecards' results",
             "",
             "The submission's, the system card's and the README's headline figures are read from these files (or a section of",
             "`docs/research.md`) by `scripts/claims.py`, and a test fails if a document and its file disagree. Failures are kept: an earlier run",
             "stays beside the latest under its own name (`-before-fixes`, `-oct28`, a date), and `docs/research.md` says what",
             "changed because of it. This page is made from the files (`scripts/results_index.py`); a test checks it's current.",
             "Pictures and sounds are never kept: only words, numbers and timings.",
             ""]
    for section, rows in cards():
        # a new section: a blank line ends the table before it (never one inside a table)
        lines += ([""] if lines[-1] else []) + [f"## {section}", "", "| Scorecard | Latest result | File | Earlier runs |",
                                                "|---|---|---|---|"]
        for c in rows:
            how = c["how"] if c["how"].startswith("a one-off") else f"`{c['how']}`"
            lines.append(f"| **{c['title']}**<br><sub>{c['what']} · {how}</sub> | {c['result']} | [`{c['file']}`]({c['file']}) | "
                         + (", ".join(f"[`{n.removesuffix('.json')}`]({n})" for n in c["earlier"]) or "") + " |")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    out = RESULTS / "README.md"
    out.write_text(build())
    print(f"wrote {out}")
