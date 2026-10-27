"""The simulated scorecard: many seeded rooms, each search scored against where things really are.

The room is the pinhole simulation in robot/sim.py: the camera model matches the Reachy Mini Lite's, SAM 3.1 and
Glimmer's picture checks are stood in for by the room's ground truth, and the robot's time is estimated from what was
measured on the real one (research.md section 9). The planners are real: --policy glimmer asks Muse Glimmer on this
computer to plan every search, exactly as on the robot.

    uv run python -m evals.sim --trials 100                      # the fixed sweep
    uv run python -m evals.sim --policy glimmer --trials 20      # Glimmer plans (needs heyandy-glimmer running)
    uv run python -m evals.sim --policy spark --trials 20        # Muse Spark plans (Model API; about $0.5, capped)

Scenarios:
  front      one thing somewhere in front (within 55 degrees), sometimes low on the table or floor
  behind     one thing past the head's reach, up to 150 degrees round
  screen     the thing, and a picture of it on a TV elsewhere
  absent     nothing there, or only a picture of it: the right answer is "I couldn't find it"
  described  two look-alikes; the person says which ("the blue one, next to the laptop")
"""
import argparse
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from heyandy_meta.agent.loop import plan_search
from heyandy_meta.agent.tools import SearchTools, side
from heyandy_meta.finder.search import Finder
from heyandy_meta.robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing

SCENARIOS = ("front", "behind", "screen", "absent", "described")
THINGS = ("glasses", "keys", "phone", "remote", "wallet", "mug")
WITHIN_DEG = 6.0
LOOK_S, SAM_S, CHECK_S = 1.4, 0.3, 2.0  # measured on the robot, 2026-10-27
# Assumed noise, so the simulation isn't perfect. Pointing: the Lite's head after one correction was within about
# 3 degrees (research.md section 9). SAM 3.1 on small things: an assumption until the physical runs measure it.
NOISE = {"point_sd_deg": 1.5, "center_sd_px": 4.0, "miss_small": 0.15, "miss": 0.03, "small_px": 55}
LOOKS = {"blue, next to the laptop": "white, by the window", "red": "green", "the big one": "the small one"}


@dataclass
class Trial:
    scenario: str
    seed: int
    label: str
    truth: tuple[float, float] | None  # where the real thing is; None when it isn't there
    request: str
    found: tuple[float, float] | None = None
    correct: bool = False
    false_find: bool = False  # pointed at the wrong thing, a picture, or anything when nothing was there
    error_deg: float | None = None
    looks: int = 0
    model_calls: int = 0
    model_s: float = 0.0
    robot_s: float = 0.0
    steps: list = field(default_factory=list)


def room_for(scenario: str, rng: random.Random) -> tuple[list[Thing], str, tuple | None, str]:
    label = rng.choice(THINGS)
    yaw = rng.uniform(-55, 55)
    pitch = rng.choice([rng.uniform(5, 22), rng.uniform(22, 32)])  # on a table, or low
    real = Thing(label, yaw, pitch, size_px=rng.randint(45, 90), score=rng.uniform(0.55, 0.95))
    where = side(yaw)
    if scenario == "front":
        return [real], label, (yaw, pitch), f"I think my {label} is {where.replace('my', 'your')}"
    if scenario == "behind":
        real.yaw = yaw = rng.choice([-1, 1]) * rng.uniform(65, 150)
        return [real], label, (yaw, pitch), f"I had my {label} behind you, on your {'left' if yaw > 0 else 'right'}"
    if scenario == "screen":
        tv = Thing(label, -yaw if abs(yaw) > 15 else yaw + 40, rng.uniform(0, 8), size_px=90, score=0.95, on_screen=True)
        return [real, tv], label, (yaw, pitch), f"where's my {label}? not the one on the TV"
    if scenario == "absent":
        things = [Thing(label, yaw, rng.uniform(0, 8), size_px=90, score=0.9, on_screen=True)] if rng.random() < 0.5 else []
        return things, label, None, f"have you seen my {label}? I can't remember where I put it"
    want, other = rng.choice(list(LOOKS.items()))
    real.looks = want
    twin = Thing(label, max(-55.0, min(55.0, yaw + rng.choice([-1, 1]) * rng.uniform(15, 40))), pitch,
                 score=real.score, looks=other)
    return [real, twin], label, (yaw, pitch), f"where's the {label}? the {want.split(',')[0]} one{want[len(want.split(',')[0]):]}"


class NoisyBody(SimBody):
    def __init__(self, room, rng):
        super().__init__(room)
        self.rng = rng
        self.pointed_at = None

    def point(self, yaw, pitch):
        super().point(yaw, pitch)
        self.pointed_at = (yaw + self.rng.gauss(0, NOISE["point_sd_deg"]), pitch + self.rng.gauss(0, NOISE["point_sd_deg"]))


class NoisySegmenter(SimSegmenter):
    def __init__(self, room, rng):
        super().__init__(room)
        self.rng = rng

    def find(self, frame, query):
        out = []
        for m in super().find(frame, query):
            small = m.box[2] - m.box[0] < NOISE["small_px"]
            if self.rng.random() < (NOISE["miss_small"] if small else NOISE["miss"]):
                continue
            m.center = (m.center[0] + self.rng.gauss(0, NOISE["center_sd_px"]),
                        m.center[1] + self.rng.gauss(0, NOISE["center_sd_px"]))
            out.append(m)
        return out


class Judge(SimJudge):
    """The ground-truth picture checks, matching a thing within a few pixels (the masks are jittered)."""

    def _thing(self, frame, mask):
        best = None
        for t in self.room.things:
            at = self.room.where_in_frame(t, frame.yaw, frame.pitch)
            if t.label == mask.label and at:
                d = math.hypot(at[0] - mask.center[0], at[1] - mask.center[1])
                if d < 25 and (best is None or d < best[0]):
                    best = (d, t)
        return best[1] if best else None


def score(t: Trial, pointed) -> Trial:
    if pointed is None:
        t.correct = t.truth is None
        return t
    t.found = (round(pointed.yaw, 2), round(pointed.pitch, 2))
    if t.truth is None:
        t.false_find = True
        return t
    t.error_deg = round(math.hypot(pointed.yaw - t.truth[0], pointed.pitch - t.truth[1]), 2)
    t.correct = t.error_deg <= WITHIN_DEG
    t.false_find = not t.correct
    return t


def run(scenario: str, seed: int, policy: str, client=None) -> Trial:
    rng = random.Random(f"{scenario}-{seed}")
    things, label, truth, request = room_for(scenario, rng)
    room = Room(things)
    body, judge = NoisyBody(room, rng), Judge(room)
    finder = Finder(body, NoisySegmenter(room, rng), check=judge.real)
    t = Trial(scenario, seed, label, truth, request)
    if policy == "fixed":
        pointed = finder.find(label)
    else:
        tools = SearchTools(finder, judge=judge)
        calls = []
        create = client.chat.completions.create

        def timed(**kw):
            start = time.monotonic()
            out = create(**kw)
            calls.append(time.monotonic() - start)
            return out

        client.chat.completions.create = timed
        try:
            if policy == "spark":
                plan = plan_search(client, request, tools)  # Muse Spark 1.3 through the Model API, under the cap
            else:
                plan = plan_search(client, request, tools, model="muse-glimmer-30B", paid=False)
        finally:
            client.chat.completions.create = create
        pointed = tools.pointed
        t.model_calls, t.model_s = len(calls), round(sum(calls), 2)
        t.steps = [(name, args) for name, args, _ in plan.steps]
    t.looks = sum(1 for e in body.log if e[0] == "capture")
    t.robot_s = round(t.looks * (LOOK_S + SAM_S) + judge.calls * CHECK_S, 1)
    if pointed is not None and body.pointed_at:
        pointed.yaw, pointed.pitch = body.pointed_at  # where the head really ended up
    return score(t, pointed)


def summary(trials: list[Trial]) -> dict:
    out = {}
    for sc in SCENARIOS:
        ts = [t for t in trials if t.scenario == sc]
        if not ts:
            continue
        errs = sorted(t.error_deg for t in ts if t.correct and t.error_deg is not None)
        out[sc] = {
            "trials": len(ts),
            "correct": sum(t.correct for t in ts),
            "false_finds": sum(t.false_find for t in ts),
            "error_median_deg": round(statistics.median(errs), 2) if errs else None,
            "looks_mean": round(statistics.mean(t.looks for t in ts), 1),
            "robot_s_mean": round(statistics.mean(t.robot_s for t in ts), 1),
            "model_s_mean": round(statistics.mean(t.model_s for t in ts), 1),
            "seconds_mean": round(statistics.mean(t.robot_s + t.model_s for t in ts), 1),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["fixed", "glimmer", "spark"], default="fixed")
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    client = None
    if args.policy == "spark":
        import os

        from openai import OpenAI

        client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
    if args.policy == "glimmer":
        from openai import OpenAI

        client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="local")
    trials = []
    for sc in args.scenarios.split(","):
        for seed in range(args.trials):
            trials.append(run(sc, seed, args.policy, client))
            t = trials[-1]
            print(f"{sc:9s} {seed:3d} {'ok ' if t.correct else 'FALSE' if t.false_find else 'miss'} "
                  f"looks {t.looks} calls {t.model_calls} {t.steps if args.policy != 'fixed' else ''}", flush=True)
    result = {"policy": args.policy, "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "within_deg": WITHIN_DEG,
              "noise": NOISE,
              "time_model": {"look_s": LOOK_S, "sam_s": SAM_S, "picture_check_s": CHECK_S},
              "summary": summary(trials), "trials": [asdict(t) for t in trials]}
    path = Path(args.out) / f"sim-{args.policy}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1))
    print(json.dumps(result["summary"], indent=1))
    print("saved", path)


if __name__ == "__main__":
    main()
