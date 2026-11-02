"""A conversation Andy isn't part of: the timing of a real one, replayed through Andy's listening, before and after.

November 2, a meeting went on near the robot for two and a half hours. Andy rightly let nearly everything pass, but
three times something woke it (its name is the founder's), and each reply opened another 20 s in which anything said
counted: 38 turns answered, 19 of them in ten minutes, until the robot was unplugged. The journal keeps, for each
utterance, only when it ended and whether Andy answered (never a word: `heyandy-app` runs with --quiet), and that's
all this reads. Each utterance is replayed through Andy's own VoiceLoop: the first of each run of answers stands for
the call that woke it ("Andy, ..."), everything else for talk that isn't to Andy; an answer takes `--turn` seconds,
and what's said meanwhile is said over it. The replay is checked by running it with the old rules (follow-ups without
limit, no room talking) and comparing with what the robot did.

And the price, in a quiet room: a conversation with Andy, its name once and then follow-ups 12 s apart.

    uv run python -m evals.room_talk                 # today's meeting, 10:40 to 13:10; numbers only
"""
import json
import subprocess
import time
from pathlib import Path

from heyandy_meta.voice.loop import WAKE, VoiceLoop

TALK = "we could move that to next week"  # what the room says: not a request, no name
CALL = "andy can you take a look"         # what woke it: the name, then chat


def timeline(since: float, until: float, run=subprocess.run) -> list[tuple[float, bool]]:
    """(when, answered) for each utterance the robot's Andy logged between two times: no words are in the journal."""
    out = run(["journalctl", "--user", "-u", "heyandy-app", "--since", f"@{since:.0f}", "--until", f"@{until:.0f}",
               "-o", "short-unix", "--no-pager"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"can't read the journal: {out.stderr.strip()}")
    rows = []
    for line in out.stdout.splitlines():
        if "turn answered" in line or "not for Andy" in line:
            rows.append((float(line.split()[0]), "turn answered" in line))
    return rows


def utterances(rows: list[tuple[float, bool]], turn_s: float, gap_s: float = 30.0) -> list[tuple[float, str]]:
    """The room's utterances to replay: an answer is logged when it ends, so its words were said `turn_s` before; the
    first answer after `gap_s` without one is the call that woke Andy, every other utterance the room's own talk."""
    out, last = [], float("-inf")
    for t, answered in rows:
        if answered:
            out.append((t - turn_s, CALL if t - last > gap_s else TALK))
            last = t
        else:
            out.append((t, TALK))
    return sorted(out)


def replay(said: list[tuple[float, str]], turn_s: float, asks: bool = True, **rules) -> dict:
    """Andy's VoiceLoop on this timeline: what it answers, what it takes without its name. Each answer asks something
    back if `asks` (Glimmer's often do: the hardest case, since a question lets one answer through)."""
    clock = [0.0]
    loop = VoiceLoop(None, clock=lambda: clock[0], **rules)
    answers, busy_until = [], float("-inf")

    class Andy:
        body = type("Body", (), {})()

        def hear(self, text):
            return "What do you think?" if asks else "Okay."

        def say(self, text):
            pass

    loop.andy = Andy()
    for t, text in said:
        clock[0] = t
        if t < busy_until:  # said over Andy's answer: run() counts it as the room talking
            loop.not_for_andy()
            continue
        reply = loop.heard(text)
        if reply is not None:
            answers.append((t, bool(WAKE.match(text))))
            busy_until = t + turn_s
            clock[0] = busy_until
            loop.awake_until = busy_until + loop.follow_up_s  # the window opens when the answer ends
    worst = max((sum(1 for a, _ in answers if s <= a < s + 600) for s, _ in answers), default=0)
    names = sum(called for _, called in answers)
    return {"answered": len(answers), "called by name": names, "without the name": len(answers) - names,
            "most in ten minutes": worst}


def conversation(then: int = 8, every_s: float = 12.0, turn_s: float = 6.0, **rules) -> dict:
    """A quiet room and a person talking with Andy: its name once, then `then` follow-ups, one every `every_s`."""
    said = [(0.0, "hey andy how are you")] + [(every_s * (i + 1), f"and tell me something else {i}") for i in range(then)]
    r = replay(said, turn_s, asks=False, **rules)
    return {"follow-ups said": then, "answered without the name": r["without the name"]}


OLD = {"follow_ups": 10**9, "room_talking": (10**9, 90.0)}


def main() -> None:
    import argparse
    import datetime as dt

    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--start", default="10:40")
    ap.add_argument("--end", default="13:10")
    ap.add_argument("--turn", type=float, default=6.0, help="seconds an answer takes, said meanwhile is said over it")
    args = ap.parse_args()
    at = lambda hm: dt.datetime.strptime(f"{args.day} {hm}", "%Y-%m-%d %H:%M").timestamp()  # noqa: E731
    rows = timeline(at(args.start), at(args.end))
    said = utterances(rows, args.turn)
    logged = sum(a for _, a in rows)
    summary = {
        "utterances": len(rows), "minutes": round((rows[-1][0] - rows[0][0]) / 60) if rows else 0,
        "the robot answered (logged)": logged,
        "replayed, the old rules": replay(said, args.turn, **OLD),
        "replayed, now": replay(said, args.turn),
        "replayed, now, Andy never asking back": replay(said, args.turn, asks=False),
        "a conversation with Andy in a quiet room, the old rules": conversation(**OLD),
        "a conversation with Andy in a quiet room, now": conversation(),
    }
    out = Path("evals/results") / f"room-talk-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": f"{args.day} {args.start}-{args.end}, "
                               f"a meeting near the robot; only times and answered-or-not read from the journal",
                               "turn_s": args.turn, "summary": summary}, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
