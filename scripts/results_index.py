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


def eyes(f: str) -> str:
    s = load(f)["summary"]
    return (f"found **{s['found, and right']} of {s['tables with it']}**, wrong {s['found, but wrong']}; "
            f"\"found\" without it {s['said found']} of {s['tables without it']}")


def eyes_live(f: str) -> str:
    s = load(f)["summary"]
    seconds = s["seconds to 'There's your cup'"]
    return (f"found in **{s['found it']} of {s['sweeps with our cup']}** sweeps ({seconds} s); "
            f"\"found\" without it {s['said found without it']}, in {s['frames']} frames, {s['seconds a frame, median']} s a frame")


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
    ("Dress rehearsal", "each line of the video's storyboard as a whole spoken turn on the robot", "evals.rehearsal", "rehearsal", rehearsal),
    ("What it's told", "\"I'm putting my passport in the top drawer\", then \"where's my passport?\"", "evals.told", "told", told),
    ("Homes", "\"my keys live here\", then \"is everything home?\" with one thing away", "evals.home", "home", home),
    ("It doesn't give up", "a miss becomes a promise: found later, pointed at and said, unprompted", "evals.lost", "lost", lost),
    ("By its ring", "\"I'm ringing my phone\": Andy turns to a ringtone, never to a voice", "evals.sound", "sound", sound),
    ("Help me reach it", "the hand-guiding on an empty table: never a hand made up", "evals.guide", "guide", guide),
    ("Are you OK?", "Andy's check of itself, once with a service stopped on purpose", "evals.selfcheck", "selfcheck", selfcheck),
    ("Under the hood", "real turns timed stage by stage", "evals.hood", "hood", hood),
    ("The room in 3D", "five looks joined by MapAnything, scan to scan", "evals.room", "room", room),
    ("Its own lens", "the focal length Andy measured with its own camera", "evals.lens", "lens", lens),
    ("Noticing", "V-JEPA 2 on clips of an empty table: nothing noticed", "evals.notice", "notice-empty", notice),
    ("Filming mode", "\"take one\": the clap heard in the robot's own sound", "evals.filming", "filming", filming),
    ("Andy Finder", "the Reachy Mini app's \"Ring it\", on the robot", "research.md section 47", "finder-ring", finder_ring),
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
    ("Languages", None, None, None, None),
    ("Spanish, written", "41 requests, several ways of asking for each ability", "evals.spanish", "spanish-written", spanish),
    ("Spanish, spoken", "the same, said by Andy's voice and heard by Omnilingual ASR", "evals.spanish --spoken", "spanish-spoken", spanish),
    ("Thirteen more languages", "eight everyday requests in each, written and spoken", "evals.languages", "languages", languages),
    ("Noticing the language", "called in one of fourteen languages, does Andy switch to it?", "evals.hear_language", "hear-language", hear),
    ("In the browser", None, None, None, None),
    ("Andy's eyes", "DINOv2 in the browser, museum photos: yours among look-alikes, and not there at all", "evals.eyes", "eyes", eyes),
    ("Andy's eyes, live", "sweeping a camera (a video of one) over our cup and its look-alikes", "evals.eyes_live", "eyes-live", eyes_live),
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


def build() -> str:
    lines = ["# The scorecards' results",
             "",
             "Every number in the README and the submission is read from a file here. Failures are kept: an earlier run",
             "stays beside the latest under its own name (`-before-fixes`, `-oct28`, a date), and `docs/research.md` says what",
             "changed because of it. This page is made from the files (`scripts/results_index.py`); a test checks it's current.",
             "Pictures and sounds are never kept: only words, numbers and timings.",
             ""]
    for title, what, module, stem, head in CARDS:
        if what is None:
            lines += [f"## {title}", "", "| Scorecard | Latest result | File | Earlier runs |", "|---|---|---|---|"]
            continue
        names = files_for(stem)
        if not names:
            continue
        main = latest(names, stem)
        try:
            text = unattended(sorted(n for n in names if re.search(r"\d{8}", n))) if head == "unattended" else head(main)
        except (KeyError, IndexError, TypeError, ValueError):
            text = "see the file"
        earlier = [n for n in names if n != main]
        how = (f"a one-off run, {module}" if module.startswith("research") else f"`uv run python {module}`" if module.endswith(".py")
               else f"`uv run python -m {module}`")
        lines.append(f"| **{title}**<br><sub>{what} · {how}</sub> | {text} | [`{main}`]({main}) | "
                     + (", ".join(f"[`{n.removesuffix('.json')}`]({n})" for n in earlier) or "") + " |")
        if title == "Filming mode":
            lines.append("")
        if title in ("Agent, Glimmer offline", "Crisis check, 15 languages", "Noticing the language"):
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    out = RESULTS / "README.md"
    out.write_text(build())
    print(f"wrote {out}")
