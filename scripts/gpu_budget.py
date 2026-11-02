"""What the whole Andy takes, measured: each of its services' memory on the two GPUs, and what would fit on one.

The question a judge asks first about "two 24 GB GPUs": who would buy that? This reads what each running service
holds (nvidia-smi's per-process memory: numbers only, no picture, no word), names it by its command line, and splits
it the way a smaller Andy would: the language model (Muse Glimmer) and everything else (seeing, hearing, the voice,
the guards, how far). Measured between turns, at rest; the cup game's tracking needs more while it runs (GPU 1 peaked
at 20.0 GB, research.md section 29).

    uv run python scripts/gpu_budget.py         # -> evals/results/gpu-budget-<date>.json
"""
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD_GB = 24.0  # one of the cards Andy runs on (and the common size of one card)
# (what's in the command line, which GPU, what it is)
SERVICES = [
    ("muse-glimmer", None, "Muse Glimmer 30B (language)"),
    ("llama-guard-3", None, "Llama Guard 3 8B (the guard)"),
    ("voice_server.py", 0, "SeamlessM4T v2 (Andy's voice)"),
    ("voice_server.py", 1, "Omnilingual ASR (hearing)"),
    ("sam_server.py", None, "SAM 3.1, DINOv2, Prompt Guard 2, V-JEPA 2 (seeing)"),
    ("depth_server.py", None, "MapAnything (how far)"),
    ("reachy-mini-daemon", None, "the robot's daemon (Pollen's: camera and sound)"),  # Andy itself holds no GPU memory
]
LANGUAGE = "Muse Glimmer 30B (language)"


def name(cmdline: str, gpu: int) -> str:
    for key, on, what in SERVICES:
        if key in cmdline and (on is None or on == gpu):
            return what
    return "other"


def measure(run=subprocess.run, cmdline=lambda pid: Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()):
    """[(what, gpu, GB)] for each process using a GPU."""
    gpus = {}
    for line in run(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], capture_output=True,
                    text=True).stdout.splitlines():
        index, uuid = [x.strip() for x in line.split(",")]
        gpus[uuid] = int(index)
    rows = []
    for line in run(["nvidia-smi", "--query-compute-apps=pid,used_memory,gpu_uuid", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True).stdout.splitlines():
        pid, mib, uuid = [x.strip() for x in line.split(",")]
        gpu = gpus.get(uuid, -1)
        try:
            what = name(cmdline(pid), gpu)
        except OSError:
            what = "other"
        rows.append((what, gpu, round(int(mib) / 1024, 1)))
    if not rows:
        raise SystemExit("no process is using a GPU: is Andy running?")
    return rows


def budget(rows) -> dict:
    by = {}
    for what, _gpu, gb in rows:
        by[what] = round(by.get(what, 0) + gb, 1)
    total = round(sum(by.values()), 1)
    language = by.get(LANGUAGE, 0.0)
    rest = round(total - language, 1)
    return {"by service, GB": by, "total GB": total, "language model GB": language, "everything else GB": rest,
            "everything else fits one 24 GB card": rest <= CARD_GB}


def main() -> None:
    rows = measure()
    b = budget(rows)
    for what, gb in sorted(b["by service, GB"].items(), key=lambda x: -x[1]):
        print(f"{gb:6.1f} GB  {what}")
    print(f"{b['total GB']:6.1f} GB in all: the language model {b['language model GB']} GB, everything else "
          f"{b['everything else GB']} GB ({'within' if b['everything else fits one 24 GB card'] else 'over'} one 24 GB card)")
    out = ROOT / "evals" / "results" / f"gpu-budget-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": "each service's GPU memory, at rest "
                               "between turns (nvidia-smi per process)", "summary": b,
                               "processes": [{"what": w, "gpu": g, "GB": gb} for w, g, gb in rows]}, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
