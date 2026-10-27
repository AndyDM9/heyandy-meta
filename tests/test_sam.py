import pytest

# The encoder is private to meta-sam-parser (pinned at 0.1.0); used here only to build test input.
from meta_sam_parser._mask_codec import _encode_raster

from heyandy_meta.models.sam import Sam31Segmenter, parse, request
from tests.fakes import FakeClient


def sam_line(left=100, top=200, w=10, h=6, filled=lambda x, y: x >= 5, c="0.9", obj=0):
    """One SAM 3.1 output line: a box (inclusive corners) and its box-local one_bit mask."""
    bits = [1 if filled(x, y) else 0 for y in range(h) for x in range(w)]
    box = f"x1={left};y1={top};x2={left + w - 1};y2={top + h - 1};w=1920;h=1080" + (f";c={c}" if c else "")
    return f"{obj}<|box;{box}|><|mask;x=0;y=0;data={h},{w},{_encode_raster(bits, w, h)}|>"


def test_centre_of_the_mask_not_the_box():
    [m] = parse("<0f>" + sam_line() + "\n", "glasses")
    assert m.box == (100, 200, 110, 206)
    assert m.area == 30
    assert m.center == pytest.approx((107.5, 203.0))  # the right half of the box is filled
    assert m.score == pytest.approx(0.9)
    assert m.outline.startswith("M") and m.outline.endswith("Z") and m.outline_scale == (1.0, 1.0)


def test_two_objects_strongest_first():
    line = "<0f>" + sam_line(c="0.4", obj=0) + "," + sam_line(left=500, c="0.8", obj=1) + "\n"
    masks = parse(line, "glasses")
    assert [m.box[0] for m in masks] == [500, 100]


def test_nothing_found_is_empty():
    assert parse("", "glasses") == []


def test_missing_score_is_none_not_zero():
    [m] = parse("<0f>" + sam_line(c=None) + "\n", "keys")
    assert m.score is None


def test_request_asks_for_small_masks_and_scores():
    r = request(b"\xff\xd8jpeg", "glasses")
    assert r["model"] == "sam-3.1"
    content = r["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "glasses"}
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert r["metadata"] == {"mask_encoding": "one_bit", "include_confidence": "true"}


def test_find_through_a_fake_client():
    client = FakeClient(sam_output="<0f>" + sam_line() + "\n")
    masks = Sam31Segmenter(client=client).find(b"jpeg", "glasses")
    assert len(masks) == 1 and masks[0].label == "glasses"
    assert client.calls[0]["model"] == "sam-3.1"
