"""What Andy costs to keep (scripts/energy.py) and whether it hears its own breathing (evals/ego_noise.py): both read
numbers only, a GPU log and the journal's times; checked here on made-up logs."""
import math
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import energy  # noqa: E402
from evals import ego_noise  # noqa: E402

HEAD = ("timestamp, index, pstate, power.draw, power.limit, temperature.gpu, clocks.sm, clocks.mem, utilization.gpu, "
        "memory.used, pcie.link.gen.gpucurrent, pcie.link.width.current, clocks_event_reasons.active, fan.speed")


def log(tmp_path, seconds):
    """seconds: [(hh:mm:ss, (state, W, load, MiB) for GPU 0, the same for GPU 1)]"""
    lines = [HEAD]
    for t, a, b in seconds:
        for g, (state, w, load, mib) in enumerate((a, b)):
            lines.append(f"2026/11/02 {t}.{100 + g}, {g}, {state}, {w}, 300.00, 40, 210, 405, {load}, {mib}, 1, 16, 0x0, 33")
    path = tmp_path / "2026-11-02.csv"
    path.write_text("\n".join(lines) + "\n2026/11/02 23:59:59.9, 0, P8")  # a line cut short when the logger stopped
    return path


def test_the_cost_of_a_day_from_the_log(tmp_path):
    busy, resting, gone = ("P2", 130.0, 20, 20000), ("P8", 18.0, 0, 20000), ("P8", 14.0, 0, 300)
    seconds = [(f"00:00:{i:02d}", ("P8", 30.0, 0, 22000), busy if i < 30 else resting) for i in range(40)]
    seconds += [(f"00:01:{i:02d}", ("P8", 28.0, 0, 300), gone) for i in range(10)]  # Andy stopped: not counted
    secs = energy.seconds(energy.rows([log(tmp_path, seconds)]))
    assert len(secs) == 40
    s = energy.summary(secs)
    gpu1 = s["cards"]["GPU 1"]
    assert gpu1["average W"] == pytest.approx((30 * 130 + 10 * 18) / 40, abs=0.1)
    assert gpu1["share of time resting"] == 0.25 and gpu1["resting W (median)"] == 18.0
    both = s["both cards"]
    assert both["kWh a day"] == pytest.approx((30 + 102) * 24 / 1000, abs=0.01)
    assert both["dollars a month"] == pytest.approx(132 * 24 / 1000 * 30.4 * 0.1816, abs=0.01)
    assert s["both cards resting"]["watts"] == 48.0


def test_a_window_that_never_rested_borrows_the_resting_power(tmp_path):
    seconds = [(f"00:00:{i:02d}", ("P8", 30.0, 0, 22000), ("P2", 135.0, 20, 20000)) for i in range(20)]
    s = energy.summary(energy.seconds(energy.rows([log(tmp_path, seconds)])), resting_w={0: 36.9, 1: 17.6})
    assert s["cards"]["GPU 1"]["resting W (median)"] is None
    assert s["both cards resting"]["watts"] == pytest.approx(30.0 + 17.6)  # its own GPU 0, the borrowed GPU 1


def test_the_window_bounds(tmp_path):
    seconds = [(f"00:00:{i:02d}", ("P8", 30.0, 0, 22000), ("P8", 18.0, 0, 20000)) for i in range(20)]
    rows = list(energy.rows([log(tmp_path, seconds)], since=datetime(2026, 11, 2, 0, 0, 5),
                            until=datetime(2026, 11, 2, 0, 0, 15)))
    assert len(rows) == 20  # 10 seconds, two cards


def test_the_price_is_eias():
    assert energy.CENTS_PER_KWH == 18.16 and "EIA" in energy.PRICE_SOURCE


# --- the breath, in the journal's times ---

def journal(times):
    return "\n".join(f"{t:.6f} host python[1]: (heard 1.4s of speech, room level 0.021; not for Andy)" for t in times)


def test_sounds_read_only_times_lengths_and_levels():
    text = journal([100.0]) + "\n101.0 host python[1]: turn answered [first word 1.2s after the person stopped]"
    assert ego_noise.sounds(text) == [(100.0, 1.4, 0.021)]


def test_sounds_that_keep_the_breaths_time_stand_out_and_others_dont():
    hz = 0.22
    period = 1 / hz
    import random

    rnd = random.Random(3)
    motors = [n * period / 2 + 0.3 + rnd.gauss(0, 0.25) for n in range(2000)]  # twice a breath, a little jitter
    people = sorted(rnd.uniform(0, 2000 * period / 2) for _ in range(2000))
    span = 2000 * period / 2
    m = ego_noise.judge([(t, 1.4, 0.02) for t in motors], hz, 0, span)
    p = ego_noise.judge([(t, 1.4, 0.02) for t in people], hz, 0, span)
    assert m["keeps time with the breath"] and m["with the breath (twice a breath)"]["z"] > 500
    assert not p["keeps time with the breath"] and p["with the breath (twice a breath)"]["z"] < 10
    assert m["control"]["largest z at any other rate"] < m["with the breath (twice a breath)"]["z"] / 10


def test_rayleigh_is_zero_for_even_times_and_one_for_locked_ones():
    hz = 0.25
    even = [i * (1 / hz) / 8 for i in range(800)]
    locked = [i * (1 / hz) for i in range(100)]
    assert ego_noise.rayleigh(even, hz)[0] == pytest.approx(0.0, abs=1e-9)
    r, z = ego_noise.rayleigh(locked, hz)
    assert r == pytest.approx(1.0) and z == pytest.approx(100.0)
    assert ego_noise.rayleigh([], hz) == (0.0, 0.0)
    assert math.isclose(sum(ego_noise.phases(locked, hz)), 100)


# --- the picture of it (scripts/breath_chart.py) ---

def test_the_chart_labels_the_one_spike_and_the_most_anywhere_else():
    import breath_chart

    points = [(0.15 + i * 0.0001, 3.0 + (i % 7) * 0.5) for i in range(1501)]
    points[700] = (points[700][0], 1926.0)
    chart, figures = breath_chart.svg(points, points[700][0])
    assert figures == {"peak at": round(points[700][0], 4), "z": 1926, "any other rate, at most": 6.0}
    assert "z 1,926" in chart and "every other rate: 6 at most" in chart


def test_the_chart_shows_the_night_the_scorecard_measured():
    import json

    from PIL import Image

    import breath_chart
    from scripts.claims import newest, summary

    shown = json.loads(Image.open(breath_chart.OUT).text["figures"])
    night = next(v for k, v in summary(newest("ego-noise")).items() if k.startswith("night"))
    assert shown["sounds an hour"] == night["an hour"]
    assert shown["z"] == round(night["with the breath (twice a breath)"]["z"])
    assert shown["any other rate, at most"] == night["control"]["largest z at any other rate"]
