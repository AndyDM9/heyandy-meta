"""What the whole Andy takes on its GPUs (scripts/gpu_budget.py): each service named, the language model apart."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gpu_budget  # noqa: E402

GPUS = "0, GPU-aaa\n1, GPU-bbb\n"
APPS = ("11, 18022, GPU-aaa\n12, 3572, GPU-aaa\n12, 5006, GPU-bbb\n13, 6338, GPU-bbb\n14, 5344, GPU-bbb\n"
        "15, 2970, GPU-bbb\n16, 256, GPU-aaa\n")
CMD = {"11": "llama-server -m models/muse-glimmer/Muse-Glimmer-30B.gguf", "12": "python local/voice_server.py",
       "13": "python local/sam_server.py --checkpoint x", "14": "llama-server -m models/llama-guard-3-8b/x.gguf",
       "15": "python local/depth_server.py", "16": "python .venv/bin/reachy-mini-daemon --headless"}


def run(cmd, **kw):
    return NS(stdout=GPUS if "--query-gpu=index,uuid" in cmd else APPS)


def test_each_service_is_named_and_the_voice_server_split_by_gpu():
    rows = gpu_budget.measure(run, CMD.__getitem__)
    names = {(w, g) for w, g, _ in rows}
    assert ("SeamlessM4T v2 (Andy's voice)", 0) in names and ("Omnilingual ASR (hearing)", 1) in names
    assert all(w != "other" for w, _, _ in rows)


def test_the_language_model_is_kept_apart_from_everything_else():
    b = gpu_budget.budget(gpu_budget.measure(run, CMD.__getitem__))
    assert b["language model GB"] == 17.6 and b["everything else GB"] == round(b["total GB"] - 17.6, 1)
    assert b["everything else fits one 24 GB card"]


def test_nothing_on_the_gpus_is_not_a_measure():
    with pytest.raises(SystemExit, match="no process"):
        gpu_budget.measure(lambda cmd, **kw: NS(stdout=GPUS if "index,uuid" in cmd[1] else ""), CMD.__getitem__)
