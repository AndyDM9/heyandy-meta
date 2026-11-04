"""The form's three answers (`docs/submission-form.md`) fit its limit and say only what the longer documents say."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORM = (ROOT / "docs" / "submission-form.md").read_text()
SOURCES = (ROOT / "docs" / "submission.md").read_text() + (ROOT / "docs" / "open-weights.md").read_text()
LIMIT = 3000
LINK = re.compile(r"https?://\S+")
FIGURE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
TITLES = (
    "Project Description",
    "Describe your use of Meta products to build the submitted project",
    "Why are Meta's models important to your solution?",
)


def answers() -> dict[str, str]:
    parts = re.split(r"^## (.+)$", FORM, flags=re.M)
    return {title: text.strip() for title, text in zip(parts[1::2], parts[2::2], strict=True)}


def test_each_of_the_forms_three_answers_is_here_and_fits():
    found = answers()
    assert tuple(found) == TITLES
    for title, text in found.items():
        assert 0 < len(text) <= LIMIT, f"{title}: {len(text)} characters"


def test_every_figure_in_the_answers_is_in_the_longer_documents():
    known = set(FIGURE.findall(LINK.sub("", SOURCES)))
    for title, text in answers().items():
        missing = set(FIGURE.findall(LINK.sub("", text))) - known
        assert not missing, f"{title}: {sorted(missing)}"


def test_the_first_answer_names_the_project_the_live_demo_and_what_came_before():
    first = answers()["Project Description"]
    assert first.startswith("Andy, by HeyAndy:")
    assert "https://huggingface.co/spaces/heyandy-ai/andy" in first
    assert "FROM BEFORE THE EVENT" in first
    assert "no model answers it" in first
