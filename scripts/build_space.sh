#!/usr/bin/env bash
# Put together the Hugging Face Space: only what the screen demo needs. No keys, tests, evaluations, robot setup or
# private notes. Output: dist/space/ (upload it with `hf upload <space> dist/space . --repo-type space`).
set -euo pipefail
cd "$(dirname "$0")/.."
out=dist/space
rm -rf "$out" && mkdir -p "$out/scripts"
cp space/Dockerfile space/README.md LICENSE "$out/"
cp scripts/demo_screen.py "$out/scripts/"
rsync -a --exclude '__pycache__' heyandy_meta "$out/"
if grep -rIl -E "MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}" "$out"; then
  echo "something that looks like a key is in the Space; stopping" >&2
  exit 1
fi
echo "built $out ($(du -sh "$out" | cut -f1))"
