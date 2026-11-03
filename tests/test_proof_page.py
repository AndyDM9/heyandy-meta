"""Andy, measured (scripts/proof_page.py): the public demo's page of every scorecard, made from the same files as
evals/results/README.md, with the claims check above them. Nothing on it is written for it: each line is a scorecard's
own, read when the Space is built."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import claims  # noqa: E402
import proof_page  # noqa: E402
import results_index  # noqa: E402
import social_card  # noqa: E402


def test_every_scorecard_is_on_the_page_with_its_file_and_how_to_run_it_again():
    page = proof_page.page()
    sections = [(t, rows) for t, rows in results_index.cards() if rows]
    cards = [c for _, rows in sections for c in rows]
    assert len(re.findall(r"<article>", page)) == len(cards) >= 40
    for c in cards:
        assert f"<h3>{proof_page.html.escape(c['title'])}</h3>" in page
        assert f'href="{proof_page.REPO}{c["file"]}"' in page
    for title, _ in sections:
        assert f'href="#{proof_page.anchor(title)}"' in page and f'id="{proof_page.anchor(title)}"' in page
    assert "**" not in page  # every bold number made strong, none left as markdown
    one_off = sum(c["how"].startswith("a one-off") for c in cards)  # a one-off run says so instead of a command
    assert page.count("<code>uv run python") == len(cards) - one_off and one_off <= 6


def test_the_claims_check_and_the_headline_figures_are_read_when_the_page_is_made():
    page = proof_page.page()
    assert f"<b>{len(claims.FIGURES)}</b>" in page
    assert ("none disagrees" in page) == (claims.problems() == [])
    for big, small in social_card.figures():
        assert f"<b>{proof_page.html.escape(big)}</b><span>{proof_page.html.escape(small)}</span>" in page
    w = claims.summary(claims.newest("open-weights-all"))
    assert f"<b>{w['matched']} of {w['files']}</b>" in page


def test_a_result_is_escaped_and_only_its_bold_becomes_strong():
    assert proof_page.rich("**3 of 4** <script>x</script> & more") == \
        "<strong>3 of 4</strong> &lt;script&gt;x&lt;/script&gt; &amp; more"
    assert proof_page.anchor("Simulated, and the agents") == "simulated-and-the-agents"


def test_the_space_builds_it_and_the_front_door_and_end_card_link_to_it():
    import build_static_space

    assert "proof.html" in build_static_space.SHARED
    page = (ROOT / "heyandy_meta" / "screen" / "page.html").read_text()
    assert 'el("a", "Every number, measured"); m.href = "proof.html"' in page
    assert "Every number, measured →" in page and "proof.html" in page
