"""The voice's tokenizer check (evals/voice_tokenizer.py): every line Andy says through SeamlessM4T v2, in each of its
fifteen languages, compared number for number with Meta's own SentencePiece model."""
import glob
import json
from pathlib import Path

from evals import voice_tokenizer as vt
from heyandy_meta.app import HEALTH_REPLY
from heyandy_meta.companion.language import LANGUAGES
from heyandy_meta.companion.safety import CRISIS_REPLY

ROOT = Path(__file__).resolve().parents[1]


def test_it_reads_every_line_andy_says_in_each_of_its_fifteen_voices():
    rows = vt.lines()
    voices = {v for v, _ in rows}
    assert voices == {lang.voice for lang in LANGUAGES.values()} and len(voices) == 15
    assert len(rows) == len(set(rows)) >= 500  # each once
    from heyandy_meta.voice.spoken import words

    def given(lang):  # as the voice server gives the model the words: numbers in words for English and Spanish
        return words(lang.crisis, "es" if lang.voice == "spa" else "en") if lang.voice in ("eng", "spa") else lang.crisis

    texts = {t for _, t in rows}
    assert all(given(lang) in texts for lang in LANGUAGES.values() if lang.crisis)  # by hand in each; English: below
    assert words(HEALTH_REPLY) in texts and words(CRISIS_REPLY) in texts
    assert "nine eight eight" in words(CRISIS_REPLY) and "nine one one" in words(HEALTH_REPLY)


def test_a_line_counts_as_the_same_only_when_every_number_is():
    rows = [("eng", "a"), ("eng", "b"), ("kor", "c")]
    s = vt.summarize(rows, [[True, 5, []], [False, 4, []], [True, 6, ["봇"]]])
    assert (s["lines"], s["same tokens"], s["tokens"], s["languages"]) == (3, 2, 15, 2) and not s["every line the same"]
    assert s["by voice"]["kor"]["characters"] == ["봇"] and s["lines with a character Meta's vocabulary hasn't"] == 1


def test_the_latest_check_found_the_copy_gives_metas_numbers_on_every_line():
    latest = sorted(glob.glob(str(ROOT / "evals" / "results" / "voice-tokenizer-*.json")))[-1]
    s = json.loads(Path(latest).read_text())["summary"]
    assert s["every line the same"] and s["same tokens"] == s["lines"] and s["languages"] == 15
