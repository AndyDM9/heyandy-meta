#!/usr/bin/env bash
# The models that run on this computer, in user space (nothing system-wide):
#   GPU 0: Muse Glimmer 30B (Q4_K_M + perception encoder + DFlash drafter) on llama.cpp's server
#   GPU 1: SAM 3.1 from the open weights (facebook/sam3.1, gated: request access first) and DINOv2 (knowing the
#          person's own things by sight) via local/sam_server.py,
#          and hearing and speaking (Meta's Omnilingual ASR and MMS-TTS) via local/voice_server.py
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
uv run -q --no-project --with huggingface_hub hf download meta-llama/Llama-Prompt-Guard-2-86M \
  --revision a8ded8e697ce7c355e395a0df51f94adb4a2fd27  # gated: request access on Hugging Face first
uv run -q --no-project --with huggingface_hub hf download facebook/dinov2-base \
  --revision f9e44c814b77203eaa57a6bdbbd535f21ede1415  # into the Hugging Face cache, where sam_server.py loads it

# Voice: Meta's Omnilingual ASR (Apache-2.0; fairseq2 pins torch 2.8 and NumPy 1) and Meta's MMS-TTS (CC-BY-NC 4.0):
# every model Andy runs is Meta's (docs/rules.md)
V="$OPT/voice"
(mkdir -p "$V" && cd "$V" && uv venv -q -p 3.12 .venv \
  && VIRTUAL_ENV=.venv uv pip install -q omnilingual-asr "transformers>=4.46" sentencepiece tiktoken protobuf soundfile \
  && VIRTUAL_ENV=.venv uv pip install -q "torchaudio==2.8.0" --index-url https://download.pytorch.org/whl/cu128 \
       --extra-index-url https://pypi.org/simple \
  && VIRTUAL_ENV=.venv uv pip install -q "pyarrow<21" \
  && .venv/bin/python -c "
from huggingface_hub import snapshot_download
for lang in ('eng', 'spa'):  # Meta's MMS-TTS, English and Spanish: the fallback voice
    snapshot_download(f'facebook/mms-tts-{lang}')
# Andy's voice, Meta's SeamlessM4T v2; its tokenizer saved where the voice server loads it offline
from transformers import AutoProcessor, SeamlessM4Tv2ForTextToSpeech
import os
AutoProcessor.from_pretrained('facebook/seamless-m4t-v2-large').save_pretrained(os.path.expanduser('~/models/seamless-m4t-v2-processor'))
SeamlessM4Tv2ForTextToSpeech.from_pretrained('facebook/seamless-m4t-v2-large')
from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
ASRInferencePipeline(model_card='omniASR_LLM_1B_v2', device='cpu')  # what the voice server runs; downloads it once
")

# Llama Guard 3 8B, the second crisis check (gated: request access first): Meta's weights converted here, 4-bit
LG="$MODELS/llama-guard-3-8b"
if [ ! -f "$LG/Llama-Guard-3-8B-Q4_K_M.gguf" ]; then
  uv run -q --no-project --with huggingface_hub hf download meta-llama/Llama-Guard-3-8B --local-dir "$LG" --exclude "original/*"
  if [ ! -d "$OPT/llama.cpp-src-$LLAMA" ]; then git clone -q --depth 1 --branch "$LLAMA" https://github.com/ggml-org/llama.cpp.git "$OPT/llama.cpp-src-$LLAMA"; fi
  (cd "$OPT/llama.cpp-src-$LLAMA" && uv run -q --no-project --with "numpy<2.3" --with sentencepiece --with "transformers>=4.45,<5" \
     --with safetensors --with protobuf --with "torch==2.8.0" --index-url https://download.pytorch.org/whl/cpu \
     --extra-index-url https://pypi.org/simple python convert_hf_to_gguf.py "$LG" --outtype bf16 --outfile "$LG/bf16.gguf")
  LD_LIBRARY_PATH="$D/cudart-llama-$LLAMA-bin-ubuntu-cuda-13.4-x64:$D/llama-$LLAMA" "$D/llama-$LLAMA/llama-quantize" \
    "$LG/bf16.gguf" "$LG/Llama-Guard-3-8B-Q4_K_M.gguf" Q4_K_M && rm "$LG/bf16.gguf"
fi

# Andy itself, with the robot and the web on the TV (a clean headless browser): run from the repository
uv sync -q --extra dev --extra robot --extra browse && uv run playwright install --only-shell chromium

echo "Done. Start them: systemctl --user link $(pwd)/deploy/heyandy-*.service && systemctl --user start heyandy-glimmer heyandy-sam heyandy-voice heyandy-guard"
