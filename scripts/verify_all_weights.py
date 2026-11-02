"""Every open-weight model Andy runs, file by file, against what Meta published, at the revision Andy loads.

For the "Best Build on Meta Open Weight Models" verification, beyond Muse Glimmer (scripts/verify_open_weights.py
asks its running server which file it serves): each of the nine models' files on this computer, as the services load
them, hashed and compared with the publisher's own record:
- on Hugging Face, the SHA-256 it publishes for each large file, and the git hash of each small one (config, tokenizer),
  at the commit the code pins (DINOv2, Prompt Guard 2 and V-JEPA 2 are pinned in local/sam_server.py, read from there)
  or the one this computer holds (the others; whether Meta's page has moved on since is said too);
- Omnilingual ASR's v2 checkpoint isn't on Hugging Face: it comes from Meta's own download server, which gives each
  file's size and an S3 ETag (an MD5, or for a large file the MD5 of each 8 MiB part's MD5), recomputed here.
Llama Guard 3 runs as a GGUF we converted and quantized from Meta's files with llama.cpp: those files are checked, and
the GGUF's own hash recorded. Our own notes beside the weights (download.sh, SHA256SUMS) aren't Meta's: listed, not
compared. Nothing is downloaded: the comparison is with the publishers' records.

    uv run python scripts/verify_all_weights.py        # a few minutes: hashes about 60 GB
"""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
HUB = HOME / ".cache" / "huggingface" / "hub"
OURS = {"download.log", "download.sh", "SHA256SUMS"}  # our own notes, never Meta's files
PART = 8 * 1024 * 1024  # the S3 multipart size Meta's download server used (9,118,733,852 bytes in 1,088 parts)


def pinned(name: str) -> str:
    """A revision exactly as local/sam_server.py pins it (so this checks what the server loads)."""
    m = re.search(rf'^{name} = "([0-9a-f]{{40}})"', (ROOT / "local" / "sam_server.py").read_text(), re.M)
    if not m:
        raise SystemExit(f"{name} isn't pinned in local/sam_server.py")
    return m.group(1)


def hub_snapshot(repo: str, hub: Path = HUB, revision: str | None = None) -> tuple[Path, str]:
    """The folder of a model in a Hugging Face cache, at a revision (default: the one it holds as main)."""
    base = hub / f"models--{repo.replace('/', '--')}"
    revision = revision or (base / "refs" / "main").read_text().strip()
    return base / "snapshots" / revision, revision


def models() -> list[dict]:
    """The nine, as Andy's services load them."""
    sam_dir = HOME / "models" / "sam3.1"
    return [
        {"name": "Muse Glimmer 30B", "repo": "meta-models/Muse-Glimmer-30B-GGUF", "revision": "main",
         "dir": HOME / "models" / "muse-glimmer",
         "files": ["Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf", "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"],
         "how": "deploy/heyandy-glimmer.service: the model and its perception encoder (the drafter isn't loaded)"},
        {"name": "SAM 3.1", "repo": "facebook/sam3.1", "revision": "main", "dir": sam_dir,
         "how": "local/sam_server.py --checkpoint ~/models/sam3.1/sam3.1_multiplex.pt"},
        {"name": "DINOv2", "repo": "facebook/dinov2-base", "revision": pinned("EMBED_REVISION"), "hub": HUB,
         "how": "local/sam_server.py EMBED_REVISION"},
        {"name": "Llama Prompt Guard 2", "repo": "meta-llama/Llama-Prompt-Guard-2-86M", "revision": pinned("GUARD_REVISION"),
         "hub": HUB, "how": "local/sam_server.py GUARD_REVISION"},
        {"name": "V-JEPA 2", "repo": "facebook/vjepa2-vitl-fpc16-256-ssv2", "revision": pinned("ACTION_REVISION"), "hub": HUB,
         "how": "local/sam_server.py ACTION_REVISION"},
        {"name": "SeamlessM4T v2", "repo": "facebook/seamless-m4t-v2-large", "hub": HUB,
         "how": "local/voice_server.py, from the cache"},
        {"name": "MapAnything", "repo": "facebook/map-anything-apache", "hub": HOME / "opt" / "mapanything" / "hf" / "hub",
         "how": "local/depth_server.py, HF_HOME=~/opt/mapanything/hf (deploy/heyandy-depth.service)"},
        {"name": "Llama Guard 3 8B", "repo": "meta-llama/Llama-Guard-3-8B", "revision": hub_snapshot(
            "meta-llama/Llama-Guard-3-8B")[1], "dir": HOME / "models" / "llama-guard-3-8b", "converted":
         "Llama-Guard-3-8B-Q4_K_M.gguf", "how": "deploy/heyandy-guard.service serves the GGUF converted here from these files"},
        {"name": "Omnilingual ASR", "url": "https://dl.fbaipublicfiles.com/mms/", "fairseq2": HOME / ".cache" / "fairseq2" / "assets",
         "files": ["omniASR-LLM-1B-v2.pt", "omniASR_tokenizer_written_v2.model"],
         "how": "local/voice_server.py --asr omniASR_LLM_1B_v2 (its card: dl.fbaipublicfiles.com/mms/)"},
    ]


def digests(path: Path) -> dict:
    """SHA-256, the git blob hash, and the S3 ETag (single MD5, and multipart over 8 MiB parts) of one file."""
    size = path.stat().st_size
    sha, git, whole = hashlib.sha256(), hashlib.sha1(f"blob {size}\0".encode()), hashlib.md5()
    parts = []
    with path.open("rb") as f:
        while chunk := f.read(PART):
            sha.update(chunk)
            git.update(chunk)
            whole.update(chunk)
            parts.append(hashlib.md5(chunk).digest())
    multipart = f"{hashlib.md5(b''.join(parts)).hexdigest()}-{len(parts)}"
    return {"size": size, "sha256": sha.hexdigest(), "git": git.hexdigest(), "md5": whole.hexdigest(), "multipart": multipart}


def published_hf(repo: str, revision: str) -> tuple[dict, str]:
    """{path: (sha256 or None, git hash, size)} as Hugging Face records them at a revision, and its main now."""
    from huggingface_hub import HfApi

    api = HfApi()
    tree = {f.path: ((f.lfs.sha256 if getattr(f, "lfs", None) else None), f.blob_id, f.size)
            for f in api.list_repo_tree(repo, revision=revision, recursive=True, expand=True) if hasattr(f, "blob_id")}
    return tree, api.model_info(repo).sha


def published_url(url: str, opener=urllib.request.urlopen) -> dict:
    req = urllib.request.Request(url, method="HEAD")
    with opener(req, timeout=30) as r:
        return {"size": int(r.headers["Content-Length"]), "etag": r.headers["ETag"].strip('"')}


def matches(local: dict, sha256: str | None, git: str | None, size: int | None) -> bool:
    if size is not None and local["size"] != size:
        return False
    return local["sha256"] == sha256 if sha256 else local["git"] == git


def etag_matches(local: dict, etag: str) -> bool:
    return local["size"] and (etag == local["multipart"] if "-" in etag else etag == local["md5"])


def check(model: dict, hashed: dict) -> dict:
    """One model's verdict from its local files' digests and its publisher's record."""
    row = {"model": model["name"], "how": model["how"], "files": 0, "matched": 0, "different": [], "not published": [],
           "ours": []}
    if "url" in model:
        row["publisher"] = model["url"]
        for name, (_path, local) in hashed.items():
            pub = published_url(model["url"] + name)
            row["files"] += 1
            ok = local["size"] == pub["size"] and etag_matches(local, pub["etag"])
            row["matched"] += ok
            if not ok:
                row["different"].append(name)
        return row
    tree, now = published_hf(model["repo"], model["revision"])
    row.update(publisher=f"huggingface.co/{model['repo']}", revision=model["revision"],
               **({"main on Hugging Face now": now} if model["revision"] not in ("main", now) else {}))
    for name, (_path, local) in hashed.items():
        if name in OURS or name == model.get("converted"):
            row["ours"].append(name)
            continue
        if name not in tree:
            row["not published"].append(name)
            continue
        row["files"] += 1
        sha, git, size = tree[name]
        if matches(local, sha, git, size):
            row["matched"] += 1
        else:
            row["different"].append(name)
    if model.get("converted"):
        row["converted here"] = {"file": model["converted"], "sha256": hashed_extra(model)}
    return row


def hashed_extra(model: dict) -> str:
    return digests(model["dir"] / model["converted"])["sha256"]


def local_files(model: dict) -> dict[str, Path]:
    """The model's files as its service loads them."""
    if "fairseq2" in model:
        found = {}
        for name in model["files"]:
            hits = sorted(model["fairseq2"].glob(f"*/{name}"))
            if hits:
                found[name] = hits[0]
        return found
    if "hub" in model:
        folder, revision = hub_snapshot(model["repo"], model["hub"], model.get("revision"))
        model["revision"] = revision
        return {str(p.relative_to(folder)): p.resolve() for p in folder.rglob("*") if p.is_file() or p.is_symlink()}
    names = model.get("files") or [p.name for p in model["dir"].iterdir() if p.is_file()]
    return {n: model["dir"] / n for n in names}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="models whose name has this in it")
    args = ap.parse_args()
    started, rows = time.time(), []
    chosen = [m for m in models() if args.only.lower() in m["name"].lower()]
    for model in chosen:
        files = local_files(model)
        if model.get("converted"):
            files.pop(model["converted"], None)
        with ThreadPoolExecutor(min(4, os.cpu_count() or 1)) as pool:
            hashed = dict(zip(files, pool.map(lambda p: (p, digests(p)), files.values())))
        row = check(model, hashed)
        rows.append(row)
        verdict = "MATCH" if row["files"] and row["matched"] == row["files"] else "DIFFERENT"
        print(f"{verdict:9} {row['model']}: {row['matched']} of {row['files']} files as {row['publisher']} publishes them"
              + (f" at {row['revision'][:12]}" if row.get("revision") else "")
              + (f"; differ: {', '.join(row['different'])}" if row["different"] else "")
              + (f"; ours: {', '.join(row['ours'])}" if row["ours"] else ""), flush=True)
    summary = {"models": len(rows), "every file matches": all(r["files"] and r["matched"] == r["files"] for r in rows),
               "files": sum(r["files"] for r in rows), "matched": sum(r["matched"] for r in rows),
               "minutes": round((time.time() - started) / 60, 1)}
    print(json.dumps(summary))
    if args.only:
        return
    out = ROOT / "evals" / "results" / f"open-weights-all-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "what": __doc__.strip().splitlines()[0],
                               "summary": summary, "models": rows}, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
