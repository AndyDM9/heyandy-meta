"""The card a shared link shows (scripts/social_card.py) and the tags that point to it (build_static_space.py)."""
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_static_space  # noqa: E402
import claims  # noqa: E402
import social_card  # noqa: E402


def test_the_card_is_the_size_x_and_github_ask_for():
    img = Image.open(social_card.OUT)
    assert img.size == (1280, 640) and social_card.OUT.stat().st_size < 1_000_000  # 2:1; GitHub's limit is 1 MB


def test_the_card_says_what_the_scorecards_say_today():
    """Made from the files; a new run that changes a figure means making it again: uv run python scripts/social_card.py"""
    assert social_card.said() == [list(f) for f in social_card.figures()]


def test_its_figures_come_from_their_sources():
    pointed, languages, models = social_card.figures()
    assert claims.unattended_since_fix() == f"{pointed[0]} unattended searches"
    assert languages[0] == "15"
    names = social_card.models()
    assert models[0] == str(len(names)) == "11" and "SAM 3.1" in names and "Muse Spark 1.3" in names


def test_a_shared_link_to_each_page_shows_the_card():
    page = "<html><head><title>Andy</title></head><body></body></html>"
    for name in build_static_space.SHARED:
        out = build_static_space.shared(page, name)
        tags = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', out))
        assert tags["og:image"] == "https://heyandy-ai-andy.static.hf.space/card.png"
        assert tags["twitter:card"] == "summary_large_image" and tags["og:image:width"] == "1280"
        assert tags["og:title"] and tags["description"] and tags["og:url"].startswith("https://")
        assert out.count("og:image\"") == 1 and out.index("</title>") < out.index("og:image")


def test_the_spaces_own_card_is_its_thumbnail():
    readme = (ROOT / "space" / "README.md").read_text().split("---")[1]
    assert "thumbnail: https://huggingface.co/spaces/heyandy-ai/andy/resolve/main/card.png" in readme
