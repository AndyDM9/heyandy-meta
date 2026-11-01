"""evals/results/README.md is the readable page of every result: made from the files, so it must be current, and every
result file must be on it (scripts/results_index.py)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import results_index  # noqa: E402


def test_the_results_page_is_current():
    assert (results_index.RESULTS / "README.md").read_text() == results_index.build(), \
        "a result changed: run uv run python scripts/results_index.py"


def test_every_result_file_is_on_the_page():
    page = (results_index.RESULTS / "README.md").read_text()
    missing = [p.name for p in results_index.RESULTS.glob("*.json") if f"({p.name})" not in page]
    assert not missing, missing
    assert not re.search(r"\| see the file \|", page.split("## Simulated")[0].replace("Earlier", ""))  # the robot's rows read


def test_no_table_is_split_by_a_blank_line():
    """A blank line between two rows ends a Markdown table: the rows after it showed as raw text (found Nov 1)."""
    lines = results_index.build().splitlines()
    assert not [i for i in range(1, len(lines) - 1) if not lines[i] and lines[i - 1].startswith("|") and lines[i + 1].startswith("|")]
