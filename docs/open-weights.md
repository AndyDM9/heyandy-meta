# Meta open-weight models in Andy, served on our own hardware

For the "Best Build on Meta Open Weight Models" verification: everything here runs on one desktop beside the robot (two
RTX 3090s, 24 GB each), with no inference provider.

| Model | Where | What it does in Andy |
|---|---|---|
| **Muse Glimmer 30B** (`meta-models/Muse-Glimmer-30B-GGUF`, Q4_K_M, with its perception encoder; its DFlash drafter is left out, its GPU memory now Andy's voice; Apache-2.0) | GPU 0, llama.cpp b11936 (`deploy/heyandy-glimmer.service`) | Everyday conversation; **plans searches and multi-part requests with the robot's tools** (12 of 12 on the agent scorecard, offline); checks pictures (a real thing, or a picture of it on a TV? which of two look-alikes did the person mean?); says what it sees ("what am I holding?") and where the person points; **translates Andy's 14 other languages** to and from English, on this computer; a third crisis check on conversation (one narrow question) |
| **SAM 3.1** (`facebook/sam3.1`, `sam3.1_multiplex.pt`) | GPU 1 (`local/sam_server.py`) | Finds things in camera frames; several watched things per glance; finds the person for reminders; **Object Multiplex** tracks every cup at once through a recorded shuffle (the cup game) |
| **Omnilingual ASR** (`omniASR_LLM_1B_v2`; Apache-2.0) | GPU 1 (`local/voice_server.py`) | Hears the person, told the language: English, or one of 14 more after "Andy, speak Russian" (or "habla español"); and told none, to notice which of them Andy was called in |
| **Llama Guard 3 8B** (`meta-llama/Llama-Guard-3-8B`; Llama 3.1 Community License; converted to GGUF and quantized to Q4_K_M here with llama.cpp b11936) | GPU 1 (`deploy/heyandy-guard.service`) | The second crisis check: reads what the person says before any other model; its self-harm category gives the 988 reply, as the word list does. And, with its own prompt for an Agent's message and Specialized Advice (S6) spelled out as Andy's policy, it reads each sentence of a model's answer before Andy says it: health advice becomes Andy's own words (held out, 11 of 25 advising answers caught, none of 168 of Andy's real answers flagged, 0.04 s; `evals/guard_replies.py`) |
| **Llama Prompt Guard 2** (`meta-llama/Llama-Prompt-Guard-2-86M`, pinned revision; Llama 4 Community License) | GPU 1 (`local/sam_server.py` `/guard`) | Reads every web page before Muse Spark's computer use sees it: a page trying to instruct Andy ends the run |
| **DINOv2** (`facebook/dinov2-base`, pinned revision; Apache-2.0) | GPU 1 (`local/sam_server.py` `/embed`) | Knows the person's own things by sight ("this is my mug"): the thing's own pixels, inside SAM 3.1's mask, as numbers; never a picture |
| **SeamlessM4T v2** (`facebook/seamless-m4t-v2-large`, its text-to-speech half, fp16, speaker 51; CC-BY-NC 4.0) | GPU 0 (`local/voice_server.py`) | **Andy's voice**, in all 15 of Andy's languages (it speaks 36), 0.3 s a sentence, made clearer for the robot's speaker (picked by ear there). Meta's Model API has no voice and every model Andy runs must be Meta's (docs/rules.md); MMS-TTS (`facebook/mms-tts-eng`, `-spa`) is the fallback |
| **MapAnything** (`facebook/map-anything-apache`; Apache-2.0) | GPU 1 (`local/depth_server.py`) | How far away a found thing is, from one camera frame; the room in 3D from five looks (`/scan`); the TV's floor plan of watched things |
| **V-JEPA 2** (`facebook/vjepa2-vitl-fpc16-256-ssv2`; MIT) | GPU 1 (`local/sam_server.py` `/action`, loaded on first use, about 0.8 GB) | Notices a watched thing put down or picked up: a 4-second clip of where something moved, judged by Meta's video world model (its Something-Something v2 head) |

**In the public demo, in the visitor's own browser** (transformers.js; nothing they show or say leaves it): **DINOv2**
(with registers, small; `onnx-community/dinov2-with-registers-small`, 8-bit) finds their own things in a photo or a
live sweep of the camera; **wav2vec 2.0** (`facebook/wav2vec2-base-960h`, Apache-2.0, as `Xenova/wav2vec2-base-960h`,
8-bit) hears "Say it", the demo's phrases decoded against the sound by CTC (`docs/research.md` sections 53, 56, 60).

Every model Andy runs is Meta's. Llama Guard 3 and Llama Prompt Guard 2: **Built with Llama**.

**Muse Spark 1.3** and **Muse Image 1.0** (Model API) are used only when online: Muse Spark gets words (planning a search
or a multi-part request, web answers with sources, harder conversation) and, only for "show me ... on the TV", screenshots
of web pages for its computer use; Muse Image gets words. Pictures and voice from the home never go to the cloud (Meta
can't turn off data retention for hackathon credits; see `research.md`), and the TV's privacy receipt shows what did.

## Every file, verified

`uv run python scripts/verify_all_weights.py` (about three minutes; it hashes about 60 GB and downloads nothing) checks
every file of the nine open-weight models as Andy's services load them against the publisher's own record: on Hugging
Face, the SHA-256 published for each large file and the git hash of each small one, at the revision the code pins
(DINOv2, Prompt Guard 2 and V-JEPA 2, read from `local/sam_server.py`) or the one this computer holds (each still Meta's
current main on November 2); Omnilingual ASR's v2 checkpoint, which isn't on Hugging Face, against Meta's own download
server (its size and its S3 ETag, recomputed here over the same 8 MiB parts). November 2
(`evals/results/open-weights-all-20261102-1535.json`):

```
MATCH  Muse Glimmer 30B      2 of 2   meta-models/Muse-Glimmer-30B-GGUF (the model and its perception encoder)
MATCH  SAM 3.1              11 of 11  facebook/sam3.1
MATCH  DINOv2                3 of 3   facebook/dinov2-base at f9e44c814b77 (pinned)
MATCH  Llama Prompt Guard 2  5 of 5   meta-llama/Llama-Prompt-Guard-2-86M at a8ded8e697ce (pinned)
MATCH  V-JEPA 2              4 of 4   facebook/vjepa2-vitl-fpc16-256-ssv2 at 4aa02df83918 (pinned)
MATCH  SeamlessM4T v2       10 of 10  facebook/seamless-m4t-v2-large at 5f8cc790b19f
MATCH  MapAnything           2 of 2   facebook/map-anything-apache at 00f9c245bbcb
MATCH  Llama Guard 3 8B     15 of 15  meta-llama/Llama-Guard-3-8B at 7327bd9f6efb (served as a GGUF converted here)
MATCH  Omnilingual ASR       2 of 2   dl.fbaipublicfiles.com/mms/ (omniASR-LLM-1B-v2.pt, its tokenizer)
54 of 54 files
```

## Verify it

```bash
systemctl --user status heyandy-glimmer heyandy-sam heyandy-voice heyandy-guard heyandy-depth heyandy-robot
uv run python scripts/verify_open_weights.py
```

The script asks the running server which file it serves, reads the GGUF's own metadata, and checks its SHA-256 against
Hugging Face. Our run on November 2 (first on October 27; kept as `evals/results/open-weights-20261102-1118.json`):

```
llama-server at http://127.0.0.1:8080 serves: Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf (alias muse-glimmer-30B, Q4_K - Medium, 2 slots)
  general.architecture: muse-glimmer
  Hugging Face meta-models/Muse-Glimmer-30B-GGUF publishes ...: sha256 4cc57c0f...7c00c6
  this file: sha256 4cc57c0f...7c00c6 -> MATCHES the published weights
```

Every turn, the TV lists the models that worked on it and where ("On this computer: SAM 3.1 x4, Muse Glimmer (picture
check)").
