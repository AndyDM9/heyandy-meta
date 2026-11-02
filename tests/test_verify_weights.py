"""Every open-weight model's files against what Meta published (scripts/verify_all_weights.py): the hashes are the
publishers' own (Hugging Face's SHA-256 and git hashes, an S3 ETag from Meta's download server)."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_all_weights as v  # noqa: E402


def test_the_hashes_are_the_publishers_own_kinds(tmp_path):
    f = tmp_path / "config.json"
    f.write_bytes(b"hello\n")
    d = v.digests(f)
    assert d["git"] == "ce013625030ba8dba906f756967f9e9ca394464a"  # `git hash-object`: how Hugging Face names a small file
    assert d["sha256"] == hashlib.sha256(b"hello\n").hexdigest() and d["md5"] == hashlib.md5(b"hello\n").hexdigest()
    assert v.etag_matches(d, d["md5"])  # a file sent in one piece: its ETag is its MD5


def test_a_large_files_etag_is_the_md5_of_its_8_mib_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "PART", 4)
    f = tmp_path / "w.pt"
    f.write_bytes(b"abcdefghij")  # parts: abcd, efgh, ij
    expect = hashlib.md5(b"".join(hashlib.md5(p).digest() for p in (b"abcd", b"efgh", b"ij"))).hexdigest() + "-3"
    d = v.digests(f)
    assert d["multipart"] == expect and v.etag_matches(d, expect) and not v.etag_matches(d, expect[:-1] + "4")


def test_a_published_sha256_decides_a_large_file_and_the_git_hash_a_small_one():
    local = {"size": 6, "sha256": "aa", "git": "bb"}
    assert v.matches(local, "aa", "zz", 6) and not v.matches(local, "cc", "bb", 6)
    assert v.matches(local, None, "bb", 6) and not v.matches(local, None, "bb", 7)


def test_the_revisions_are_the_ones_the_server_pins():
    text = (Path(v.ROOT) / "local" / "sam_server.py").read_text()
    for name in ("EMBED_REVISION", "GUARD_REVISION", "ACTION_REVISION"):
        assert v.pinned(name) in text and len(v.pinned(name)) == 40


def test_a_file_that_differs_is_named_and_our_own_notes_are_never_compared(tmp_path, monkeypatch):
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    (tmp_path / "config.json").write_bytes(b"{}")
    (tmp_path / "SHA256SUMS").write_bytes(b"ours")
    model = {"name": "X", "repo": "facebook/x", "revision": "c" * 40, "dir": tmp_path, "how": "test"}
    hashed = {n: (p, v.digests(p)) for n, p in v.local_files(model).items()}
    good = {"model.safetensors": (hashlib.sha256(b"weights").hexdigest(), None, 7),
            "config.json": (None, hashed["config.json"][1]["git"], 2)}
    monkeypatch.setattr(v, "published_hf", lambda repo, rev: (good, "c" * 40))
    row = v.check(model, hashed)
    assert (row["files"], row["matched"], row["different"], row["ours"]) == (2, 2, [], ["SHA256SUMS"])
    bad = dict(good, **{"model.safetensors": ("0" * 64, None, 7)})
    monkeypatch.setattr(v, "published_hf", lambda repo, rev: (bad, "d" * 40))
    row = v.check(model, hashed)
    assert row["different"] == ["model.safetensors"] and row["main on Hugging Face now"] == "d" * 40
