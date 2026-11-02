"""Silence inside Andy's answers: between a streamed answer's sentences, and before its first, with each sentence's
voice made as it's said, or made ahead as it arrives (voice/speaker.py prepare, app.py _ahead).

Andy's real voice service (SeamlessM4T v2 on this computer) makes each sentence; a pretend speaker takes exactly as long
as the sentence's sound and plays nothing, so the robot stays quiet. The turn's own order is kept: each sentence read by
Llama Guard 3 first (its measured 0.05 s), and the head turning to the person before the first (its measured 0.9 s,
the hood's "move", November 2). The answers are written here: no person's words.

    uv run python -m evals.speech_gaps --save        # a minute or so; -> evals/results/speech-gaps-<date>.json
"""
import argparse
import json
import statistics as st
import time
from pathlib import Path

from heyandy_meta.voice.local import LocalVoice
from heyandy_meta.voice.speaker import Speaker

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = [
    ["It's a lovely question.", "The moon is about two hundred and thirty-eight thousand miles away.",
     "Light from it reaches us in a little over a second.", "Would you like to know more?"],
    ["Good morning to you too.", "It looks like a quiet day ahead, with nothing on your list until the afternoon.",
     "Shall I keep an eye on your keys while you get ready?"],
    ["I'm well, thanks for asking.", "I've been keeping an eye on the table, and your glasses are still where you left them.",
     "How are you feeling today?"],
    ["That's a good one.", "A day on Venus is longer than its year.", "It turns very slowly, and backwards.",
     "Isn't that strange?"],
]
CHECK_S, TURN_S = 0.05, 0.9


def run(speaker: Speaker, events: list, ahead: bool, sleep=time.sleep, clock=time.monotonic) -> list[dict]:
    rows = []
    for answer in ANSWERS:
        events.clear()
        t0 = clock()
        if ahead:  # the answer as it arrives (the cloud's comes whole): each sentence's voice started at once
            for sentence in answer:
                speaker.prepare(sentence)
        for i, sentence in enumerate(answer):
            sleep(CHECK_S)
            if i == 0:
                sleep(TURN_S)
            speaker(sentence)
        starts = [t for kind, t in events if kind == "start"]
        ends = [t for kind, t in events if kind == "end"]
        rows.append({"first sound s": round(starts[0] - t0, 2),
                     "silences s": [round(b - a, 2) for a, b in zip(ends, starts[1:])]})
    return rows


def summary(rows: list[dict]) -> dict:
    gaps = [g for r in rows for g in r["silences s"]]
    return {"answers": len(rows), "first sound, median s": round(st.median(r["first sound s"] for r in rows), 2),
            "silence between sentences, median s": round(st.median(gaps), 2),
            "silence between sentences, longest s": round(max(gaps), 2),
            "silence in all the answers s": round(sum(gaps), 1), "silences": len(gaps)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="http://127.0.0.1:8092")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    events: list = []

    def play(audio, rate):  # takes as long as the sound would, plays nothing
        events.append(("start", time.monotonic()))
        time.sleep(len(audio) / rate)
        events.append(("end", time.monotonic()))

    speaker = Speaker(LocalVoice(args.voice), play)
    speaker("Ready.")  # the voice service warm, as it is between turns
    out = {"made as said (before)": [], "made ahead (now)": []}
    for _ in range(args.rounds):  # alternated, so neither has the warmer service
        out["made as said (before)"] += run(speaker, events, ahead=False)
        out["made ahead (now)"] += run(speaker, events, ahead=True)
    result = {k: summary(v) for k, v in out.items()}
    for k, s in result.items():
        print(f"{k:22} first sound {s['first sound, median s']} s; between sentences {s['silence between sentences, median s']}"
              f" s (longest {s['silence between sentences, longest s']}), {s['silence in all the answers s']} s in "
              f"{s['answers']} answers")
    if args.save:
        path = ROOT / "evals" / "results" / f"speech-gaps-{time.strftime('%Y%m%d-%H%M')}.json"
        path.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": __doc__.strip().splitlines()[0],
                                    "check s": CHECK_S, "head turn s": TURN_S, "summary": result, "answers": out}, indent=1))
        print(f"saved {path}")


if __name__ == "__main__":
    main()
