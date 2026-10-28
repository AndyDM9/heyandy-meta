# Meta open-weight models in Andy, served on our own hardware

For the "Best Build on Meta Open Weight Models" verification: everything here runs on one desktop beside the robot (two
NVIDIA RTX 3090s, 24 GB each), with no inference provider.

| Model | Where | What it does in Andy |
|---|---|---|
| **Muse Glimmer 30B** (`meta-models/Muse-Glimmer-30B-GGUF`, Q4_K_M, with its perception encoder and DFlash drafter; Apache-2.0) | GPU 0, llama.cpp b11936 (`deploy/heyandy-glimmer.service`) | Everyday conversation; **plans searches with the robot's tools** when the person gives a hint; checks pictures (a real thing, or a picture of it on a TV? which of two look-alikes did the person mean?) |
| **SAM 3.1** (`facebook/sam3.1`, `sam3.1_multiplex.pt`) | GPU 1 (`local/sam_server.py`) | Finds things in camera frames; several watched things per glance; finds the person for reminders; **Object Multiplex** tracks every cup at once through a recorded shuffle (the cup game) |
| **Omnilingual ASR** (`omniASR_LLM_1B_v2`; Apache-2.0) | GPU 1 (`local/voice_server.py`) | Hears the person, told the language is English |

Not Meta: Kokoro-82M (Apache-2.0) speaks, because Meta has no open text-to-speech model.

**Muse Spark 1.3** (Model API) is used only when online, only for words: planning a search from what the person said, and
web answers with sources. Pictures and voice from the home never go to the cloud (Meta can't turn off data retention
for hackathon credits; see `research.md`).

## Verify it

```bash
systemctl --user status heyandy-glimmer heyandy-sam heyandy-voice
uv run python scripts/verify_open_weights.py
```

The script asks the running server which file it serves, reads the GGUF's own metadata, and checks its SHA-256 against
Hugging Face. Our run (2026-10-27):

```
llama-server at http://127.0.0.1:8080 serves: Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf (alias muse-glimmer-30B, Q4_K - Medium, 2 slots)
  general.architecture: muse-glimmer
  Hugging Face meta-models/Muse-Glimmer-30B-GGUF publishes ...: sha256 4cc57c0f...7c00c6
  this file: sha256 4cc57c0f...7c00c6 -> MATCHES the published weights
```

Every turn, the TV lists the models that worked on it and where ("On this computer: SAM 3.1 x4, Muse Glimmer (picture
check)").
