"""The form's three answers (`docs/submission-form.md`) fit its limit and say only what the longer documents say."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORM = (ROOT / "docs" / "submission-form.md").read_text()
SOURCES = "".join((ROOT / f).read_text() for f in ("docs/submission.md", "docs/open-weights.md", "docs/system-card.md", "README.md",
                                                    "docs/research.md", "evals/results/unattended-20261031-0900.json"))
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


def test_no_file_name_becomes_a_link_on_the_form():
    """The form makes a link of anything shaped like an address: research.md opened a page selling that domain."""
    for title, text in answers().items():
        names = re.findall(r"\b[\w-]+\.(?:md|cpp|py|json|sh|html|txt)\b", LINK.sub("", text))
        assert not names, f"{title}: {names}"


def test_a_judges_key_goes_in_a_file_git_ignores():
    example = (ROOT / ".env.example").read_text()
    assert re.search(r"^MODEL_API_KEY=$", example, flags=re.M)  # no value, ever
    assert "HEYANDY_PAID_CALLS=1" in example
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()
    assert ".env.example" in (ROOT / "README.md").read_text()


def test_the_first_answer_names_the_project_the_live_demo_and_what_came_before():
    first = answers()["Project Description"]
    assert first.startswith("Andy, by HeyAndy:")
    assert "https://huggingface.co/spaces/heyandy-ai/andy" in first
    assert "FROM BEFORE THE EVENT" in first
    assert "no model answers it" in first and "25 of 34" in first  # and how often the rule catches one
