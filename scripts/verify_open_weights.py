"""Show that Andy runs on Meta's open-weight Muse Glimmer, served on this computer, for the hackathon's verification.

It asks the running llama-server which file it serves, reads that GGUF file's own metadata (architecture, name),
and checks the file's SHA-256 against the one Hugging Face publishes for meta-models/Muse-Glimmer-30B-GGUF.

    uv run python scripts/verify_open_weights.py            # about a minute: hashes 17 GB
    uv run python scripts/verify_open_weights.py --no-hash
"""
import argparse
import hashlib
import json
import struct
import urllib.request
from pathlib import Path

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


def gguf_metadata(path: Path, keys=("general.architecture", "general.name", "general.license")) -> dict:
    """Read a few string keys from a GGUF header (format: magic, version, counts, then key/type/value entries)."""
    found = {}
    with path.open("rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError(f"{path} is not a GGUF file")
        version, _tensors, kv_count = struct.unpack("<IQQ", f.read(20))
        found["gguf.version"] = version

        def string():
            (n,) = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")

        def skip(t):
            if t == 8:
                string()
            elif t == 9:
                et, n = struct.unpack("<IQ", f.read(12))
                for _ in range(n):
                    skip(et)
            else:
                f.read(SIZES[t])

        for _ in range(kv_count):
            key = string()
            (t,) = struct.unpack("<I", f.read(4))
            if t == 8 and key in keys:
                found[key] = string()
            else:
                skip(t)
            if all(k in found for k in keys):
                break
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--no-hash", action="store_true")
    args = ap.parse_args()
    props = json.load(urllib.request.urlopen(args.server + "/props"))
    path = Path(props["model_path"])
    print(f"llama-server at {args.server} serves: {path.name} (alias {props.get('model_alias')}, "
          f"{props.get('model_ftype')}, {props.get('total_slots')} slots)")
    for k, v in gguf_metadata(path).items():
        print(f"  {k}: {v}")
    tree = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{REPO}/tree/main"))
    published = {f["path"]: f.get("lfs", {}).get("oid") for f in tree}
    print(f"  Hugging Face {REPO} publishes {path.name}: sha256 {published.get(path.name)}")
    if not args.no_hash:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(1 << 24):
                h.update(chunk)
        ok = h.hexdigest() == published.get(path.name)
        print(f"  this file: sha256 {h.hexdigest()} -> {'MATCHES' if ok else 'DOES NOT MATCH'} the published weights")


if __name__ == "__main__":
    main()
