"""Andy's public pages for people who see less well or tap less surely (evals/accessibility.py): axe-core's WCAG 2.2
checks, and text contrast measured from the pixels where axe can't decide it."""
import functools
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from evals import accessibility as A  # noqa: E402
from heyandy_meta.screen.server import serve  # noqa: E402
from heyandy_meta.screen.state import ScreenState  # noqa: E402


def test_contrast_is_wcags():
    assert round(A.ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert 4.4 < A.ratio((0x77, 0x77, 0x77), (255, 255, 255)) < 4.6  # #777 on white: the classic near miss
    assert A.large(24, 400) and A.large(18.7, 700) and not A.large(18.7, 400) and not A.large(16, 700)


def test_a_texts_transparency_is_laid_over_what_is_behind_it():
    dark = [(14, 22, 19)] * 99
    full, _ = A.measured((245, 243, 239), 1.0, dark)
    faded, _ = A.measured((245, 243, 239), 0.4, dark)
    assert full > 15 and faded < full and faded > 3
    p5, worst = A.measured((16, 36, 29), 1.0, [(251, 250, 245)] * 96 + [(30, 40, 35)] * 4)  # a few stray dark pixels
    assert p5 > 14 and worst < 1.2  # the 5th percentile decides, the worst is kept


def test_only_the_axe_recorded_here_is_used(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "AXE_CACHE", tmp_path / "axe.min.js")
    with pytest.raises(SystemExit, match="SHA-256"):
        A.axe(fetch=lambda url: b"/* not axe */")


@pytest.fixture(scope="module")
def axe_js():
    try:
        return A.axe()
    except Exception as e:  # noqa: BLE001 - no network and no cached copy: nothing to check with
        pytest.skip(f"axe-core unavailable: {e}")


def test_the_help_and_a_dial_of_old_sightings_pass_axe_and_contrast(axe_js):
    """The two places the audit found faults on November 2: the help's headings and its scrolling on a phone, and the
    dial that faded the name of a thing seen hours ago to 3:1 (now its dot fades, its name has a halo)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from demo_screen import SCENES, show

    def snapshot(name):
        st = ScreenState()
        show(st, name)
        return st.snapshot()

    server = serve(ScreenState(), port=0, scenes={n: functools.partial(snapshot, n) for n in SCENES})
    try:
        rows = A.audit(f"http://127.0.0.1:{server.server_address[1]}/", axe_js,
                       which=[("help", "?scene=help", None), ("memory", "?scene=memory", None), ("sound", "?scene=sound", None)])
    finally:
        server.shutdown()
    assert len(rows) == 6
    for r in rows:
        assert r["violations"] == {}, (r["state"], r["width"], r["violations"])
        assert r["contrast too low"] == [], (r["state"], r["width"], r["contrast too low"])
    assert sum(r["contrast measured"] for r in rows) > 20  # it did measure
