#!/usr/bin/env bash
# The models that run on this computer, in user space (nothing system-wide):
#   GPU 0: Muse Glimmer 30B (Q4_K_M + perception encoder + DFlash drafter) on llama.cpp's server
#   GPU 1: SAM 3.1 from the open weights (facebook/sam3.1, gated: request access first) and DINOv2 (knowing the
#          person's own things by sight) via local/sam_server.py,
#          and hearing and speaking (Meta's Omnilingual ASR, Kokoro-82M) via local/voice_server.py
# Needs: an NVIDIA driver for CUDA 13, uv, gh (or curl), and `hf auth login` for SAM 3.1.
set -euo pipefail
OPT=${OPT:-$HOME/opt}
MODELS=${MODELS:-$HOME/models}
LLAMA=b11936            # Glimmer needs b10353 or newer
SAM3=f1647e8d0c1d280991f4d1b7d974c2704537fe66
mkdir -p "$OPT" "$MODELS"

# llama.cpp: the official CUDA build, checked against the release's sha256 digests
D="$OPT/llama.cpp-$LLAMA"
if [ ! -x "$D/llama-$LLAMA/llama-server" ]; then
  mkdir -p "$D/dl"
  for f in "llama-$LLAMA-bin-ubuntu-cuda-13.4-x64.tar.gz" "cudart-llama-$LLAMA-bin-ubuntu-cuda-13.4-x64.tar.gz"; do
    digest=$(gh api "repos/ggml-org/llama.cpp/releases/tags/$LLAMA" --jq ".assets[] | select(.name==\"$f\") | .digest")
    curl -sSL -o "$D/dl/$f" "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA/$f"
    echo "${digest#sha256:}  $D/dl/$f" | sha256sum -c
    tar -xzf "$D/dl/$f" -C "$D"
  done
fi

# Muse Glimmer 30B GGUF (Apache-2.0), about 20 GB
uv run -q --no-project --with huggingface_hub hf download meta-models/Muse-Glimmer-30B-GGUF --local-dir "$MODELS/muse-glimmer" \
  --include "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf" --include "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf" \
  --include "dflash-Muse-Glimmer-30B-Q4_K_M.gguf" --include "LICENSE" --include "USAGE_POLICY.md"

# SAM 3.1: Meta's sam3 code at a pinned commit, in its own environment, and the checkpoint (3.5 GB)
if [ ! -d "$OPT/sam3" ]; then git clone -q https://github.com/facebookresearch/sam3.git "$OPT/sam3"; fi
git -C "$OPT/sam3" checkout -q "$SAM3"
(cd "$OPT/sam3" && uv venv -q -p 3.12 .venv \
  && VIRTUAL_ENV=.venv uv pip install -q torch==2.10.0 torchvision --index-url https://download.pytorch.org/whl/cu128 \
  && VIRTUAL_ENV=.venv uv pip install -q -e . pillow einops pycocotools psutil opencv-python-headless "transformers>=5,<6")
uv run -q --no-project --with huggingface_hub hf download facebook/sam3.1 --local-dir "$MODELS/sam3.1"
uv run -q --no-project --with huggingface_hub hf download facebook/dinov2-base \
  --revision f9e44c814b77203eaa57a6bdbbd535f21ede1415  # into the Hugging Face cache, where sam_server.py loads it

# Voice: Omnilingual ASR (Apache-2.0; fairseq2 pins torch 2.8 and NumPy 1) and Kokoro-82M (Apache-2.0)
V="$OPT/voice"
(mkdir -p "$V" && cd "$V" && uv venv -q -p 3.12 .venv \
  && VIRTUAL_ENV=.venv uv pip install -q omnilingual-asr "kokoro>=0.9.4" soundfile \
  && VIRTUAL_ENV=.venv uv pip install -q "torchaudio==2.8.0" --index-url https://download.pytorch.org/whl/cu128 \
       --extra-index-url https://pypi.org/simple \
  && VIRTUAL_ENV=.venv uv pip install -q "pyarrow<21" \
       "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl" \
  && .venv/bin/python -c "
from huggingface_hub import hf_hub_download
for f in ['config.json', 'kokoro-v1_0.pth'] + [f'voices/{v}.pt' for v in ['am_michael', 'af_heart', 'bf_emma', 'bm_george',
                                                                           'em_alex', 'ef_dora']]:  # Spanish: em_alex, ef_dora
    hf_hub_download('hexgrad/Kokoro-82M', f)
from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
ASRInferencePipeline(model_card='omniASR_LLM_1B_v2', device='cpu')  # what the voice server runs; downloads it once
")

# Andy itself, with the robot and the web on the TV (a clean headless browser): run from the repository
uv sync -q --extra dev --extra robot --extra browse && uv run playwright install --only-shell chromium

echo "Done. Start them: systemctl --user link $(pwd)/deploy/heyandy-*.service && systemctl --user start heyandy-glimmer heyandy-sam heyandy-voice"
