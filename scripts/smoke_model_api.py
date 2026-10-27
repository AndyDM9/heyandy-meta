"""The first paid calls to Meta's Model API, small and capped: run once the hackathon credits show on Billing.

    MODEL_API_KEY=... HEYANDY_PAID_CALLS=1 uv run python scripts/smoke_model_api.py [--image a_public_photo.jpg]

1. Muse Spark answers a short question.
2. Muse Spark plans a search with the robot's tools, in the simulated room (words only).
3. Muse Spark answers with web search, and its sources.
4. SAM 3.1 through the API finds a thing in a picture: a public photo you pass, or the drawn sample (no home pictures).

Each step is logged in the spend ledger (logs/spend.jsonl) and refused past the $140 cap; the whole run costs a few
cents. A summary (latencies, request IDs, costs; no keys) is saved to evals/results/.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heyandy_meta.agent.loop import plan_search  # noqa: E402
from heyandy_meta.agent.tools import SearchTools  # noqa: E402
from heyandy_meta.budget import Budget  # noqa: E402
from heyandy_meta.companion import answers  # noqa: E402
from heyandy_meta.finder.search import Finder  # noqa: E402
from heyandy_meta.models.muse_spark import MuseSparkModel  # noqa: E402
from heyandy_meta.models.sam import Sam31Segmenter  # noqa: E402
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing  # noqa: E402


def step(name, results, fn):
    start = time.monotonic()
    try:
        out = fn()
        results.append({"step": name, "ok": True, "seconds": round(time.monotonic() - start, 2), "result": out})
        print(f"ok   {name} ({results[-1]['seconds']} s): {out}")
    except Exception as e:  # noqa: BLE001 - report every step, whatever fails
        results.append({"step": name, "ok": False, "seconds": round(time.monotonic() - start, 2),
                        "error": f"{type(e).__name__}: {e}"[:400],
                        "request_ids": getattr(e, "request_ids", None)})
        print(f"FAIL {name}: {results[-1]['error']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="a public photo (not of a home) for SAM 3.1 through the API")
    ap.add_argument("--query", default="mug")
    args = ap.parse_args()
    budget = Budget()
    before = budget.spent()
    spark = MuseSparkModel(budget=budget, max_tokens=120)
    results = []
    step("muse-spark chat", results, lambda: spark.chat("In one short sentence: what is a tabletop robot?").text)

    def plan():
        room = Room([Thing("reading glasses", -50.0, 20.0)])
        tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)))
        p = plan_search(spark.client, "I think I left my reading glasses by the TV on the right", tools, budget=budget)
        return {"steps": [(t, a) for t, a, _ in p.steps], "pointed": bool(tools.pointed), "calls": p.calls}

    step("muse-spark plans a search with tools", results, plan)

    def web():
        a = answers.ask(spark.client, "When is the next full moon?", budget=budget)
        return {"answer": a.text, "sources": a.sources[:3]}

    step("muse-spark web search with sources", results, web)

    def sam():
        if args.image:
            image = Path(args.image).read_bytes()
        else:
            from demo_screen import sample_frame

            image = sample_frame()[0]
        masks = Sam31Segmenter(budget=budget).find(image, args.query)
        return [{"box": m.box, "score": m.score, "center": [round(c) for c in m.center]} for m in masks[:3]]

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    step(f"sam-3.1 through the API: {args.query!r}", results, sam)
    spent = round(budget.spent() - before, 4)
    print(f"spent about ${spent} (estimated from list prices; Billing has the real figure)")
    out = Path("evals/results") / f"smoke-model-api-{time.strftime('%Y%m%d-%H%M')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "spent_usd": spent, "steps": results},
                              indent=1, default=str))
    print("saved", out)


if __name__ == "__main__":
    main()
