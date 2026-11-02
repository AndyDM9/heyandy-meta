"""After uploading the Space: is what Hugging Face serves exactly what was built? Every built file there at the same
size (and, for the large ones kept with LFS, the same SHA-256), nothing on the Space that the build doesn't have, and
whether the Space is private or public. November 2 it found Hugging Face's own template stylesheet from the Space's
first commit still there (uploads add and replace, never remove).

    uvx --from huggingface_hub hf upload heyandy-ai/andy dist/space-static . --repo-type space
    uvx --from huggingface_hub python scripts/verify_space.py          # --remove-extra deletes what the build hasn't
"""
import argparse
import hashlib
import sys
from pathlib import Path

KEEP = {".gitattributes"}  # Hugging Face's own: which files are kept with LFS


def compare(local: dict[str, Path], remote: dict) -> dict:
    """What differs between the built files (path -> file) and the Space's (path -> its tree entry)."""
    return {
        "missing": sorted(set(local) - set(remote)),
        "extra": sorted(set(remote) - set(local) - KEEP),
        "size": sorted(k for k in local if k in remote and remote[k].size != local[k].stat().st_size),
        "sha256": sorted(k for k in local if k in remote and getattr(remote[k], "lfs", None)
                         and remote[k].lfs.sha256 != hashlib.sha256(local[k].read_bytes()).hexdigest()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", default="heyandy-ai/andy")
    ap.add_argument("--built", type=Path, default=Path(__file__).resolve().parents[1] / "dist" / "space-static")
    ap.add_argument("--remove-extra", action="store_true", help="delete the Space's files the build doesn't have")
    args = ap.parse_args()
    from huggingface_hub import HfApi  # here, not above: compare() is tested where it isn't installed (CI)

    api = HfApi()
    local = {str(p.relative_to(args.built)): p for p in args.built.rglob("*") if p.is_file()}
    remote = {f.path: f for f in api.list_repo_tree(args.space, repo_type="space", recursive=True, expand=True)
              if hasattr(f, "size")}
    diff = compare(local, remote)
    if args.remove_extra and diff["extra"]:
        for path in diff["extra"]:
            api.delete_file(path, args.space, repo_type="space", commit_message=f"Remove {path}: not in the build")
        diff["extra"] = []
    private = api.space_info(args.space).private
    print(f"{len(local)} built files; the Space: {'PRIVATE' if private else 'public'}")
    for what, paths in diff.items():
        print(f"  {what}: {', '.join(paths) if paths else 'none'}")
    sys.exit(1 if any(diff.values()) else 0)


if __name__ == "__main__":
    main()
