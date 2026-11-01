"""This repository goes public and to the judges: none of it may name our other hackathon entry, and none of it may
call the people Andy is for by the two age words we never use (sources cited by their web address are fine). An Oct 31
note named the other entry and nothing caught it; this does. The words are put together below so this file doesn't
hold them."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OTHER_ENTRY = re.compile("|".join(["andy" + sep + "companion" for sep in "-_ "] + ["ne" + "bius", "cos" + "mos"]), re.I)
WORDS = re.compile(r"\b(?:sen" + r"iors|elder" + r"ly)\b", re.I)
URL = re.compile(r"https?://\S+|\b[\w.-]+\.(?:com|org|net|gov|edu|io|ai)/\S*")


def tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.split("\0") if p and not p.startswith("docs/private/")]


def texts():
    for path in tracked():
        try:
            yield path.relative_to(ROOT), path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # pictures, sounds, fonts, models


def test_no_file_names_the_other_entry():
    hits = [f"{p}:{n}" for p, text in texts() for n, line in enumerate(text.splitlines(), 1) if OTHER_ENTRY.search(line)]
    assert not hits, hits


def test_no_file_uses_the_age_words_outside_a_cited_address():
    hits = [f"{p}:{n}" for p, text in texts() for n, line in enumerate(text.splitlines(), 1)
            if WORDS.search(URL.sub("", line))]
    assert not hits, hits


def test_no_file_names_the_other_hackathons_sponsor_except_in_a_commands_name():
    """The founder's rule (Oct 28): the entries are kept apart, so the hardware is "GPUs with CUDA", "RTX 3090s"; the
    driver's own commands (nvidia-smi, nvidia-ml-py) keep their names."""
    brand = re.compile("nvi" + "dia", re.I)
    command = re.compile("nvi" + r"dia[-_](?:smi|ml)|pynvml", re.I)
    hits = [f"{p}:{n}" for p, text in texts() for n, line in enumerate(text.splitlines(), 1)
            if brand.search(command.sub("", line))]
    assert not hits, hits
