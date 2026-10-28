"""The agent scorecard: requests with more than one part, planned by Muse Spark or Muse Glimmer over Andy's abilities.

Each request runs on a fresh Andy in the simulated room (the robot's camera model, things at known directions), with
the real model planning: Muse Spark through the Model API (words only; there are no pictures in the simulated room),
or Muse Glimmer on this computer. A request scores only if everything asked happened: the robot pointed at the right
thing, the reminder is set for the right time with the right words, the right things are kept an eye on. The model's
words don't count; what the robot did does.

    uv run python -m evals.agent --brain spark
    uv run python -m evals.agent --brain glimmer
"""
import argparse
import datetime as dt
import json
import os
import statistics
import tempfile
import time
from pathlib import Path

from heyandy_meta.agent.assistant import needs_agent
from heyandy_meta.app import Andy
from heyandy_meta.companion.reminders import Reminders
from heyandy_meta.memory.places import Places
from heyandy_meta.models.common import Reply
from heyandy_meta.robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing

NOW = dt.datetime(2026, 10, 28, 9, 30).timestamp()  # a Wednesday morning


def at(hour: int, minute: int = 0) -> float:
    return dt.datetime(2026, 10, 28, hour, minute).timestamp()


class Device:
    def chat(self, prompt, history=()):
        return Reply("Okay.", "device")


def room() -> list[Thing]:
    return [Thing("glasses", -30.0, 20.0), Thing("keys", 45.0, 25.0), Thing("remote", -60.0, 18.0),
            Thing("phone", 20.0, 22.0), Thing("wallet", 60.0, 20.0), Thing("charger", 120.0, 25.0),
            Thing("mug", 10.0, 15.0, looks="blue, next to the laptop"), Thing("mug", -15.0, 15.0, looks="red")]


def pointed(body, yaw: float, within: float = 6.0) -> bool:
    return any(e[0] == "point" and abs(e[1] - yaw) <= within for e in body.log)


def reminder(a, hour, minute, *words) -> bool:
    return any(abs(r.at - at(hour, minute)) < 60 and all(w in r.text.lower() for w in words) for r in a.reminders.upcoming())


def reminder_in(a, minutes, *words) -> bool:
    return any(abs(r.at - (NOW + minutes * 60)) < 90 and all(w in r.text.lower() for w in words)
               for r in a.reminders.upcoming())


def used(a, tool) -> bool:
    return any(s.startswith(tool + ":") for s in a.screen.snapshot()["steps"])


# (request, setup, check). Written for this scorecard; the agent's prompt wasn't tuned on them.
CASES = [
    ("Find my glasses and remind me at 5 pm to clean them", None,
     lambda a, b: pointed(b, -30) and reminder(a, 17, 0, "clean")),
    ("Where are my keys? And keep an eye on them from now on", None,
     lambda a, b: pointed(b, 45) and "keys" in a.places.watching()),
    ("Keep an eye on my wallet and my glasses", None,
     lambda a, b: {"wallet", "glasses"} <= set(a.places.watching())),
    ("Remind me in 10 minutes to stretch, and at 6 pm to call Sam", None,
     lambda a, b: reminder_in(a, 10, "stretch") and reminder(a, 18, 0, "call", "sam")),
    ("Forget my wallet and then find my phone", lambda a: a.places.watch("wallet"),
     lambda a, b: "wallet" not in a.places.watching() and pointed(b, 20)),
    ("Look for my keys and my glasses", None, lambda a, b: pointed(b, 45) and pointed(b, -30)),
    ("Find the blue mug, not the red one, and remind me at 3 pm to wash it", None,
     lambda a, b: pointed(b, 10) and not pointed(b, -15, 3.0) and reminder(a, 15, 0, "wash")),
    ("Find my charger, I think it's behind you, and then keep an eye on it", None,
     lambda a, b: pointed(b, 120) and "charger" in a.places.watching()),
    ("What reminders do I have, and where did you last see my keys?",
     lambda a: (a.reminders.add("take the bins out", at(19), now=NOW), a.places.watch("keys"),
                a.places.saw("keys", 45.0, 25.0, when=NOW - 1200)),
     lambda a, b: used(a, "list_reminders") and used(a, "what_i_remember")),
    ("Where's the remote? Also remind me at noon to water the plants", None,
     lambda a, b: pointed(b, -60) and reminder(a, 12, 0, "water", "plants")),
    ("Look at what's on the table and then find my phone", None,
     lambda a, b: used(a, "look_and_tell") and pointed(b, 20)),
    ("Find my glasses, then my keys, then remind me in an hour to leave", None,
     lambda a, b: pointed(b, -30) and pointed(b, 45) and reminder_in(a, 60, "leave")),
]


def andy(tmp: Path, brain: str) -> tuple[Andy, SimBody]:
    r = Room(room())
    body = SimBody(r)
    spark = glimmer = None
    if brain == "spark":
        from openai import OpenAI

        spark = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
    else:
        from openai import OpenAI

        glimmer = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="local", timeout=120)
    a = Andy(body, SimSegmenter(r), Device(), Places(tmp / "places.json"), Reminders(tmp / "reminders.json"),
             spark=spark, judge=SimJudge(r), glimmer=glimmer, online=brain == "spark", clock=lambda: NOW)
    return a, body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", choices=["spark", "glimmer"], default="spark")
    args = ap.parse_args()
    rows = []
    for request, setup, check in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            a, body = andy(Path(tmp), args.brain)
            if setup:
                setup(a)
            start = time.monotonic()
            try:
                reply = a.hear(request)
                error = ""
            except Exception as e:  # noqa: BLE001 - a crash scores as a failure, with its name
                reply, error = "", f"{type(e).__name__}: {e}"
            seconds = time.monotonic() - start
            ok = not error and bool(check(a, body))
            steps = a.screen.snapshot()["steps"]
            rows.append({"request": request, "agent": needs_agent(request), "ok": ok, "seconds": round(seconds, 1),
                         "steps": steps, "reply": reply, "error": error})
            print(f"{'ok ' if ok else 'NO '} {seconds:5.1f}s {request}\n     steps: {steps}\n     said: {reply[:160]}"
                  + (f"\n     error: {error}" if error else ""), flush=True)
    right = sum(r["ok"] for r in rows)
    summary = {"brain": args.brain, "requests": len(rows), "right": right,
               "seconds_median": round(statistics.median(r["seconds"] for r in rows), 1),
               "went_to_the_agent": sum(r["agent"] for r in rows), "when": time.strftime("%Y-%m-%d %H:%M")}
    print(json.dumps(summary))
    out = Path(f"evals/results/agent-{args.brain}.json")
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print("saved", out)


if __name__ == "__main__":
    main()
