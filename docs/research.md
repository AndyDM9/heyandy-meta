# Research for the build plan

**Gathered 2026-10-27.** The plan built on it is [build-plan.md](build-plan.md). Prices, versions and dates change, so each
one is dated. ⚠ marks a fact we couldn't confirm from Meta or the organizers; check it before relying on it.

## 1. The hackathon

- **Dates (ET):**
  - Kickoff October 26, 12 PM.
  - Submissions due **November 4, 9:00 PM**, on the Cerebral Valley platform.
  - Judging November 4 to 8; finals and winners November 9.
  - Source: [the event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) and the organizers' emails of
    October 26.
- **Tracks:**
  - Indie: "creativity, technical ambition, and whether it works".
  - Startup: "technical execution and whether it holds up in production".
  - Source: [Meta's event page](https://dev.meta.ai/events/global-hackathon).
- **Themes:**
  - "Build for Your World".
  - "Push the Frontier": "software, robotics, manufacturing … Give a machine a new capability … understand and control a
    physical system".
- **Judging** (the official rules, [waiver page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver)):
  - Impact 30%, including "whether it fits one of the problem statements".
  - Use of Meta AI tooling 25%: "beyond a basic integration … surfaced unexpected capabilities".
  - Technical depth and execution 20%.
  - Demo 25%.
- **Original work** (the official rules): the submission must be "original work product", solely owned. Open-source
  parts are allowed if their licences are followed. The organizers and partners get a perpetual, royalty-free licence to
  use the submission, including in marketing.
- ⚠ **Rules seen only in a participant's copy of the signed-in participant guide**
  ([meta-ai-hackathon/meta-hack](https://github.com/meta-ai-hackathon/meta-hack), `info/`, read October 27):
  - "New work only: demo shows only what you built during the event; unclear contribution = immediate disqualification".
  - The repository must be public; teams of up to 4; one submission per team.
  - The **3-minute demo video** is the primary judging artifact.
  - Judging has three stages: a pass/fail gate (fits a theme and genuinely uses Meta's models), the scored rubric, then
    the top 5 of each track in a live final.
  - **The disqualified list**, quoted there as verbatim: "Any project using AI to generate and give medical advice e.g. AI
    Mental Health Advisor, skin blemish detector, etc.; Basic RAG Applications; Simple Image Analyzers; simple 'AI for
    Education' Chatbots; AI Job Application Screener; AI Nutrition Coach; Personality Analyzers; Sports analyzers or
    coaches; Anything political or involving war".
  - **Prizes:**
    - Startup track: $250K, $150K, $75K, $50K, $25K.
    - Indie track: $150K, $100K, $75K, $50K, $25K.
    - Bonuses: Most Viral $20K (X engagement through November 8); Best Build on Open Weight Models $10K; Community Vote
      $10K; Best Agentic Use-Case $5K; Best Creative Build $5K (Muse Image or Muse Wonder).
  - **Workshops** (12–1 PM ET): Agents 101 on October 27; Agents 102 on October 28; Fireworks on October 30.
    Office hours weekdays 10–11 AM ET in Discord.
  - **Partner credits:**
    - Baseten: $100. The hackathon needs the model name `meta-models/muse-spark-open-1026`.
    - Modal: $100, for the first 1,000.
    - Fireworks: $25, shortlisted teams only.

## 2. Meta Model API

Docs: [overview](https://dev.meta.ai/docs/overview), [quickstart](https://dev.meta.ai/docs/quickstart),
[pricing and limits](https://dev.meta.ai/docs/pricing-rate-limits).

- **Base URL:** `https://api.meta.ai/v1`.
- **Auth:** a bearer key from the environment variable `MODEL_API_KEY`.
- **Compatibility:** works with the OpenAI SDK (Responses and Chat Completions), the Anthropic SDK and LiteLLM. There is
  no Meta SDK; use `pip install openai`.
- **Muse Spark 1.3** (`muse-spark-1.3`):
  - About 1M tokens of context; 131k output.
  - Input: text, image, PDF and video. Output: text.
  - Tool calls (parallel and streamed), structured output, prompt caching, a reasoning-effort setting, and a `web_search`
    tool.
  - Price: $1.25 per 1M input tokens, $0.15 cached, $4.25 output.
  - No published latency.
- **The Contributor tier** (`muse-spark-1.3-contributor`): $0.10 in and $0.20 out per 1M tokens, but **Meta may train on
  the data**. Never use it with pictures or conversations from a home.
- **Muse Wonder** (`muse-wonder-1.0`, preview): the most capable model; $4 in and $20 out per 1M tokens.
- **Muse Image** (`muse-image-1.0`): $0.01 per image.
- **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`): speech to text at $0.18 an hour, realtime over
  `wss://api.meta.ai/v1/asr/realtime`. It has no text to speech.
- **Muse Code:** a coding agent for the terminal (`muse`). It's a tool for writing code, not something in the product.
- **Rate limits** (per team):
  - Spark Standard: 3,000 requests and 4M tokens a minute.
  - `sam-3.1`: 3,000 requests a minute.
- **Hackathon credits:** $150 a person.
  - Claim by November 4, 9 PM ET, through the form in the October 26 email.
  - A card is required.
  - Set a spend limit on Billing.
- ⚠ **Unknown: data retention** for API inputs on the Standard tier. Ask in office hours before sending pictures of a
  home.

## 3. SAM 3.1

- **Through the API** ([media segmentation](https://dev.meta.ai/docs/media-segmentation),
  [SAM overview](https://dev.meta.ai/docs/sam/overview)):
  - The request: `POST /v1/responses` with `model: "sam-3.1"`, one user message holding an `input_text` noun phrase
    ("glasses") and an `input_image` (a URL, or uploaded through `/v1/files`) or a video. Box and point prompts are also
    accepted.
  - The output is special-token text: one line per frame, with a box (`x1,y1,x2,y2,w,h` in source pixels) and an encoded
    mask for each object.
  - Options: `metadata: {"include_confidence": "true"}` adds a 0–1 score; `metadata: {"mask_encoding": "one_bit"}`
    gives the smallest masks.
  - No match gives an empty output.
  - Parse with `pip install meta-sam-parser`
    ([client libraries](https://dev.meta.ai/docs/sam/client-libraries)).
  - Price: $2.50 per 1,000 images; $0.20 per 1,000 video frames.
- **What 3.1 adds over SAM 3** (released November 19, 2025): SAM 3.1 (March 27, 2026) adds *Object Multiplex*, joint
  tracking of many objects in video, about 7x faster at 128 objects on an H100. The image detector is unchanged.
  Source: [RELEASE_SAM3p1.md](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md).
- **Open weights:**
  - [`facebook/sam3.1`](https://huggingface.co/facebook/sam3.1) on Hugging Face: gated (request access), under Meta's
    SAM License.
  - Code in `facebookresearch/sam3`: Python ≥ 3.12, PyTorch ≥ 2.7, CUDA ≥ 12.6.
  - Transformers has SAM 3, but **not SAM 3.1**. The model card (read 2026-10-27) says the repository "hosts only the
    SAM 3.1 model checkpoints — there is no Hugging Face Transformers integration". Use the `facebookresearch/sam3` code.
  - Size: about 474M parameters, a 3.45 GB checkpoint.
- ⚠ **Speed** (community figures, [SAM3-TensorRT](https://github.com/dataplayer12/SAM3-TensorRT)):

  | Hardware | PyTorch | TensorRT |
  |---|---|---|
  | RTX 3090 | 438 ms an image | 75 ms |
  | Jetson Orin NX | 6.6 s | 950 ms |

  It is "not realtime on a Jetson Nano". The figure of about 10–12 GB of GPU memory in FP16 is from a blog.
- ⚠ **Small objects:** SAM 3 may resize its input below 1080p, which would shrink glasses (50–80 px wide at 1080p). We
  test full frames against tiles on Day 1.

## 4. Meta open-weights models we can run

- **Muse Glimmer 30B** (August 10, 2026) ([docs](https://dev.meta.ai/docs/muse-glimmer),
  [get the model](https://dev.meta.ai/docs/muse-glimmer/get-the-model),
  [Ollama](https://ollama.com/library/muse-glimmer)):
  - A dense model, text and image in, distilled from Muse Spark.
  - **Apache-2.0**, with no attribution or naming rule.
  - 128k context; trained on 100+ languages (⚠ no Spanish benchmark found).
  - Weights:
    - `meta-models/Muse-Glimmer-30B-GGUF`: Q4_K_M is about 17 GB and fits a 24 GB GPU, plus a vision projector of
      about 1.4 GB.
    - `ollama run muse-glimmer` needs Ollama ≥ 0.32.7.
  - Runs on llama.cpp, vLLM and SGLang.
  - From the GGUF model card ([meta-models/Muse-Glimmer-30B-GGUF](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF),
    read 2026-10-27):
    - **llama.cpp build `b10353` or newer is required.** Older builds don't know the architecture.
    - `--jinja` is required.
    - **It's a reasoning model:** `llama-server` returns the thinking separately in `reasoning_content`. For speech, set
      `Reasoning effort: low` in the system prompt and measure the time to first word.
    - **Files:** Q4_K_M at 16.8 GB, plus the perception encoder (`mmproj`, 1.4 GB, needed for images), plus a **DFlash
      drafter** (1.6 GB) for speculative decoding: "same outputs, faster decode". All three take about 20 GB on one 24 GB
      GPU.
    - **Suggested sampling:** `--temp 1.0 --top-p 0.95 --top-k 64`.
- **Muse Spark Open** (October 15, 2026): 816B total, 42B active parameters. It's too big for our desktop; only on partner
  credits. Its licence requires "Built with Muse Spark Open".
- **For a Jetson Orin Nano 8 GB** (not this entry): Glimmer won't fit; Llama 3.2 1B or 3B would. The Llama licence
  requires "Built with Llama" and a model name starting with "Llama".

## 5. Our own earlier work, as the baseline

From our earlier prototype (public, Apache-2.0), read on 2026-10-27. Its finder code is in `its own repository`.

- **The finder:**
  - Four views at yaw 55, 18, −18 and −55°, pitch 15° down.
  - Each view cut into six tiles at full resolution, read by a vision-language model.
  - Up to two close-ups, each checked by the model before pointing.
  - Pixel to angle: a pinhole model with fx 1116, cx 953 and cy 542 at 1920×1080, from Pollen's Reachy Mini Lite
    calibration.
  - The head reaches ±60° yaw and ±35° pitch.
- **Measured:**

  | Where | Result | Time |
  |---|---|---|
  | Simulation (seed 11, 30 trials, a vision-language model on this desktop) | Pointed 22 of 23, false finds 0 of 7, error median 1.95° | 4.80 s a search (model time only) |
  | Real robot, 2026-10-20 | Pointed 3 of 9, never wrong; all six misses on a chair about 74° to the side, past the head's reach | Median 12.4 s to point |

  A search cost about $0.005.
- **For a fair comparison:**
  - The simulation can be replayed on the same trials.
  - The October 20 real-robot pictures were deleted after scoring, so the real comparison needs new recorded tries, read
    by both finders.
- **Its ideas never tried:** an open-vocabulary detector first, 4K stills, a lower second row of views. No segmentation.
- **Related winner:** Mira (TreeHacks 2026, Most Impactful) also finds lost things for older adults. Our difference to
  state is the physical pointing, the memory of where things were put, offline operation, and published measurements.

## 6. Hardware on hand (2026-10-27)

- **Body:** a Reachy Mini Lite on USB to the desktop. The robot runs SDK `reachy-mini==1.12.0rc1`.
- **Desktop:** 2× RTX 3090, 24 GB each. Both were in use by our earlier prototype on October 27: 21.7 GB and 7.2 GB.
- **No Jetson** is owned yet.
