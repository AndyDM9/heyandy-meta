#!/usr/bin/env bash
# MapAnything (Meta Reality Labs and Carnegie Mellon; Apache-2.0 weights) in its own environment, for
# local/depth_server.py: how far away a found thing is. About 12 GB on disk (7.6 GB of it PyTorch).
set -euo pipefail
cd "$HOME/opt" && mkdir -p mapanything && cd mapanything
[ -d src ] || git clone https://github.com/facebookresearch/map-anything.git src
git -C src checkout 3d10cf7  # the commit measured on 2026-10-30
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -e ./src
# Fetch the weights once (facebook/map-anything-apache, 4.9 GB), so the service can run offline.
HF_HOME="$PWD/hf" TORCH_HOME="$PWD/torch" CUDA_VISIBLE_DEVICES=1 .venv/bin/python -c \
  "from mapanything.models import MapAnything; MapAnything.from_pretrained('facebook/map-anything-apache')"
echo "Done. Then: systemctl --user link $(dirname "$0")/../deploy/heyandy-depth.service && systemctl --user enable --now heyandy-depth"
