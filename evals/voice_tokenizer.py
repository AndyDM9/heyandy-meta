"""Andy's voice reads its words with Meta's tokenizer: the copy it loads, against Meta's own files, token for token.

SeamlessM4T v2 turns each line into tokens before it says it. The voice server loads its tokenizer from
~/models/seamless-m4t-v2-processor, a copy scripts/setup-local-models.sh made from Meta's with transformers'
save_pretrained (so it loads offline at once). Those three files are written by the library, not Meta's bytes, so the
weights check (scripts/verify_all_weights.py, which verifies Meta's own tokenizer.model and the rest byte for byte)
can't cover them. This checks what matters about them: every line Andy says through SeamlessM4T v2, in each of its
fifteen languages (its hand-written lines and their English, the AI line, the crisis reply and the health line, the
demo's story in every language, its scenes, Andy's eyes and the introductions), made into the text the voice server
gives the model (numbers and times in words, as it does) and turned into tokens by the copy and by Meta's own files from
the cache, each told the line's language as the voice server tells it. On the processor, in the voice service's own
environment; nothing is said, sent or downloaded.

    uv run python -m evals.voice_tokenizer        # -> evals/results/voice-tokenizer-<time>.json
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_PY = Path.home() / "opt" / "voice" / ".venv" / "bin" / "python"
COPY = Path.home() / "models" / "seamless-m4t-v2-processor"
REPO = "facebook/seamless-m4t-v2-large"
HUB = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{REPO.replace('/', '--')}"
VOICE = ROOT / "heyandy_meta" / "screen" / "voice"

# Run in the voice service's environment (it has transformers and sentencepiece): the copy and Meta's files, offline.
COMPARE = r"""
import json, os, sys
os.environ["HF_HUB_OFFLINE"] = "1"
import sentencepiece, transformers
from transformers import AutoProcessor
copy = AutoProcessor.from_pretrained(sys.argv[1])
meta = sentencepiece.SentencePieceProcessor(model_file=sys.argv[2])
tok, out = copy.tokenizer, []
for voice, text in json.load(sys.stdin):
    ids = copy(text=text, src_lang=voice)["input_ids"]
    # Meta's numbers, as the model reads them: its language's tag, each piece one more than SentencePiece's, the end
    want = [tok.convert_tokens_to_ids(f"__{voice}__"), *(i + 1 for i in meta.encode(text)), tok.eos_token_id]
    # what Meta's own vocabulary has no piece for (SentencePiece's <unk>, id 0): the model reads "unknown" there too
    unknown = sorted({p for p, i in zip(meta.encode(text, out_type=str), meta.encode(text)) if i == meta.unk_id()})
    out.append([ids == want, len(ids), unknown])
print(json.dumps({"transformers": transformers.__version__, "sentencepiece": sentencepiece.__version__, "rows": out}))
"""


def lines() -> list[tuple[str, str]]:
    """(voice, text) for every line Andy says through SeamlessM4T v2, once each, as the voice server gives it the text."""
    sys.path.insert(0, str(ROOT))
    from heyandy_meta.app import HEALTH_REPLY
    from heyandy_meta.companion.language import LANGUAGES, PHRASES
    from heyandy_meta.companion.safety import CRISIS_REPLY, DISCLOSURE
    from heyandy_meta.voice.spoken import words

    voice = {code: lang.voice for code, lang in LANGUAGES.items()}
    said = set()

    def add(code: str, text: str) -> None:
        v = voice[code]
        if text and text.strip():  # numbers and times in words, for English and Spanish, as local/voice_server.py does
            said.add((v, words(text, "es" if v == "spa" else "en") if v in ("eng", "spa") else text))

    for code, table in PHRASES.items():
        for english, line in table.items():
            add("en", english)
            add(code, line)
    for code, lang in LANGUAGES.items():
        add(code, lang.disclosure)
        add(code, lang.crisis)
    for text in (HEALTH_REPLY, CRISIS_REPLY, DISCLOSURE):
        add("en", text)
    for code, lang in json.loads((VOICE / "story-in.json").read_text())["languages"].items():
        for chapter in lang.get("chapters", {}).values():
            add(code, chapter["said"])
    for chapter in json.loads((VOICE / "story.json").read_text())["chapters"].values():
        add("en", chapter["text"])
    for scene in json.loads((VOICE / "scenes.json").read_text())["scenes"].values():
        add(scene["lang"], scene["text"])
    for code, lines_ in json.loads((VOICE / "find.json").read_text())["languages"].items():
        for line in lines_.values():
            add(code, line["text"])
    for code, clip in json.loads((VOICE / "voice.json").read_text())["clips"].items():
        add(code, clip["text"])
    return sorted(said)


def meta_model() -> Path:
    """Meta's own SentencePiece model, as the cache holds it (verified by scripts/verify_all_weights.py)."""
    found = sorted((HUB / "snapshots").glob("*/tokenizer.model"))
    if not found:
        raise SystemExit(f"no {REPO} tokenizer.model in {HUB}: run scripts/setup-local-models.sh")
    return found[-1]


def compare(rows: list[tuple[str, str]], python: Path = VOICE_PY, copy: Path = COPY) -> dict:
    out = subprocess.run([str(python), "-c", COMPARE, str(copy), str(meta_model())], input=json.dumps(rows),
                         capture_output=True,
                         text=True, timeout=1800)
    if out.returncode != 0:
        raise SystemExit("the voice environment couldn't compare them: " + out.stderr.strip()[-400:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def summarize(rows: list[tuple[str, str]], compared: list) -> dict:
    by: dict[str, dict] = {}
    for (voice, _), (same, n, unknown) in zip(rows, compared, strict=True):
        b = by.setdefault(voice, {"lines": 0, "same tokens": 0, "tokens": 0, "lines with a character Meta's vocabulary "
                                  "hasn't": 0, "characters": set()})
        b["lines"] += 1
        b["same tokens"] += bool(same)
        b["tokens"] += n
        b["lines with a character Meta's vocabulary hasn't"] += bool(unknown)
        b["characters"].update(unknown)
    for b in by.values():
        b["characters"] = sorted(b["characters"])
    return {"lines": len(rows), "languages": len(by), "same tokens": sum(b["same tokens"] for b in by.values()),
            "tokens": sum(b["tokens"] for b in by.values()),
            "every line the same": all(b["same tokens"] == b["lines"] for b in by.values()),
            "lines with a character Meta's vocabulary hasn't": sum(b["lines with a character Meta's vocabulary hasn't"]
                                                                  for b in by.values()), "by voice": by}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows = lines()
    result = compare(rows)
    snapshots = sorted((HUB / "snapshots").glob("*"))
    meta = snapshots[-1] if snapshots else None
    record = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "what": "Andy's voice's tokenizer (the copy it loads) against Meta's own files, token for token, on every line "
                "Andy says through SeamlessM4T v2: evals/voice_tokenizer.py",
        "copy": {"dir": "~/models/seamless-m4t-v2-processor", "made by": "scripts/setup-local-models.sh (save_pretrained)",
                 "files": {p.name: sha256(p) for p in sorted(COPY.iterdir()) if p.is_file()}},
        "meta": {"repo": REPO, "revision": meta.name if meta else None,
                 "tokenizer.model": sha256(meta / "tokenizer.model") if meta and (meta / "tokenizer.model").exists()
                 else None},
        "transformers": result["transformers"], "sentencepiece": result["sentencepiece"],
        "summary": summarize(rows, result["rows"]),
        "differ": [{"voice": v, "text": t} for (v, t), (same, *_) in zip(rows, result["rows"], strict=True) if not same],
    }
    out = ROOT / "evals" / "results" / f"voice-tokenizer-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    s = record["summary"]
    print(f"{s['same tokens']} of {s['lines']} lines in {s['languages']} languages the same, token for token "
          f"({s['tokens']:,} tokens); saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
