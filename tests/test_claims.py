"""Every figure the submission and the system card state is read from its source (scripts/claims.py): a scorecard's
file, or the research section that records a one-off measurement."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import claims  # noqa: E402


def test_every_figure_in_the_submission_and_the_system_card_says_what_its_source_says():
    assert claims.problems() == []


def test_a_figure_edited_by_hand_has_no_source():
    assert claims.unsourced("x", "250 of 253 unattended searches ended in a point") == []
    found = claims.unsourced("x", "251 of 253 unattended searches ended in a point")
    assert len(found) == 1 and "251 of 253" in found[0]


def test_the_best_run_quoted_for_one_that_varies_has_no_source():
    """The fall shot took 16.5 s once and 27.1 s once: one run's time alone isn't the robot's."""
    assert claims.unsourced("x", "points at the phone (16.5 s on the robot)")
    assert min(claims.emergency_runs()) == 16.5 and max(claims.emergency_runs()) == 27.1 and len(claims.emergency_runs()) == 4


def test_a_new_run_that_changes_a_figure_is_caught(monkeypatch):
    real = claims.summary

    def leaky(name):
        s = real(name)
        return {**s, "camera_pictures_to_cloud": 1} if name == "privacy-audit.json" else s

    monkeypatch.setattr(claims, "summary", leaky)
    found = claims.disagreements()
    assert any(f.startswith('"no camera picture reached the cloud (24 taken)"') and "1 camera pictures" in f for f in found)
    assert any(f.startswith('"0 of 24 camera pictures') for f in found)


def test_a_one_off_figure_must_still_be_in_its_research_section(monkeypatch):
    monkeypatch.setattr(claims, "research_section", lambda number: "" if number == 50 else "anything")
    assert any("9.6 s sooner" in f and "§50" in f for f in claims.disagreements())


def test_figures_are_read_as_prose_bold_and_broken_across_lines():
    assert claims.unsourced("x", "**250 of\n  253** unattended searches") == []
    assert claims.plain("a **13 of 15**\n   right") == "a 13 of 15 right"


def test_what_counts_as_a_figure():
    found = [m.group(0) for m in claims.FIGURE.finditer("now 0 of 72, then 1,000 of 1,000; 7.8 s; 9%; 31 times in 42; 4.1°; 2 GPUs")]
    assert found == ["0 of 72", "1,000 of 1,000", "7.8 s", "9%", "31 times in 42", "4.1°"]


def test_every_source_is_a_file_that_exists_a_value_in_the_code_or_a_research_section():
    names = {p.name for p in claims.RESULTS.glob("*.json")}
    for f in claims.FIGURES:
        if f.reads is None:
            assert f.quote and "research.md §" in f.source
        elif f.source.startswith("code: "):
            assert f.source.split()[1].startswith("heyandy_meta.")
        else:
            stem = f.source.split()[0].rstrip(",").removesuffix("-*")
            assert any(n.startswith(stem) for n in names), f.source


def test_a_value_set_in_the_code_is_read_from_the_code(monkeypatch):
    import dataclasses

    from heyandy_meta.finder.search import Finder

    monkeypatch.setitem(Finder.__dataclass_fields__, "aim_corrections", dataclasses.field(default=3))
    assert any("at most twice" in f and "three times" in f for f in claims.disagreements())


def test_a_badge_is_read_as_what_it_says():
    readme = ('<img src="https://img.shields.io/badge/On%20the%20robot-250%20of%20253%20pointed-1e5f4a?style=for-the-badge">'
              '<img src="https://img.shields.io/badge/%E2%96%B6%20Try%20it-the%2075--second%20story-ffcf5c?style=x">'
              '<!-- <img src="https://img.shields.io/badge/Watch-the%203--minute%20video-ffcf5c"> -->')
    assert claims.badges(readme) == "On the robot 250 of 253 pointed · ▶ Try it the 75-second story"
    assert claims.unsourced("README.md", claims.badges(readme)) == []
    assert claims.unsourced("README.md", claims.badges(readme.replace("250%20of", "251%20of")))


def test_the_readme_is_checked_down_to_its_proof_and_its_built_during_the_event():
    text = "a 1 of 2\n## Proof\nb 3 of 4\n## Built during the event, and before\nc 5 of 6\n## Run it\nd 7 of 8\n"
    found = " ".join(claims.unsourced("README.md", claims.checked("README.md", text)))
    assert "1 of 2" in found and "5 of 6" in found and "3 of 4" not in found and "7 of 8" not in found


def test_markup_is_not_prose():
    assert claims.unsourced("x", '<img src="eyes.webp" width="49%" alt="85% like the one you showed me">') == []
    assert claims.unsourced("x", "[the file](evals/results/x-50%25.json)") == []
