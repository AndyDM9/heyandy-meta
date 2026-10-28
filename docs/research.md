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
- **Data retention, answered** by Connor (Meta) in #office-hours, 2026-10-27, 11:01 AM ET: "there is a ZDR option,
  but it's usually applied for large businesses, and couldn't be enabled for the $150 token credit… If you're concerned
  about sharing real homes with our platform, you may want to create a simulated home environment for development and
  demo purposes." **So:** frames sent to the API are kept under normal terms, and pictures from a real home must not
  go there.

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
  - **Base64 data URLs work** for `input_image` (another participant succeeded with them; hackathon #questions,
    2026-10-27).
  - ⚠ **Intermittent `404 model_not_found` on new accounts**, for both `sam-3.1` and `muse-spark-1.3` (#questions,
    Oct 26–27). One participant saw about half their Spark calls fail, and most SAM calls. Meta (Oct 27, 11:07 AM):
    "no known routing issue", and it asked for request IDs. Our clients retry twice, keep the request IDs, then fall back
    to the device.
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

## 7. A physical companion: what older adults use, competitors, rules (read 2026-10-27)

**What gets used** (strongest evidence first):
- **Answers to questions** (news, weather, facts) is the use that held steady in a 3-week, 7-home Echo Dot study,
  while music and reminders faded ([Pradhan, Lazar & Findlater 2020](https://thatlab.umd.edu/papers/2020_UseOf.pdf)).
- In the Michigan poll (2,883 adults 50+, Feb 2025), 80% of voice-assistant users said it helps them live
  independently at home, and 92% want to know whether information comes from a person or an AI
  ([NPHA 2025](https://ihpi.umich.edu/national-poll-healthy-aging/national-findings/how-older-adults-use-and-think-about-ai)).
- **Reminders** are wanted, but use stays low when people don't trust them to fire (Pradhan). In Smarr et al.
  (2014), older adults accepted reminders from a robot but wanted a person to decide about medication.
- **Finding things:** small evidence (a 2026 interview study of 4 people aged 70–90, [arXiv 2603.14182](https://arxiv.org/pdf/2603.14182)),
  and no competitor does it.

**Competitors.** ElliQ (about $40 a month), Alexa+, Gemini for Home and Ollie talk, remind and answer. None finds or
points at physical objects. Alexa Together was discontinued May 21, 2025.

**US rules for companion chatbots.** A conversational robot with memory is likely in scope.
- **California SB 243** (in effect Jan 1, 2026) requires:
  - a clear notice that it's an AI;
  - a published crisis protocol that refers people to crisis services.
- **New York** (in effect Nov 5, 2025) requires:
  - saying it's an AI at the start and at least every three hours;
  - efforts to detect self-harm and refer people to help.
- The FDA's general-wellness guidance (Jan 6, 2026) keeps products outside device rules if they make no
  diagnose-or-treat claims.

**What this means for Andy:**
- It says it's an AI, out loud, at the start and every three hours.
- It has a short published crisis protocol: it gives the 988 line and never counsels.
- No health, medication, mood or wellbeing features or claims.
- Memory is opt-in, visible and deletable.

**From Meta's API for companion functions:**
- **Muse Spark's `web_search` tool:** $2.50 per 1,000 searches plus tokens. It returns `url_citation`
  annotations, which give the sources ([search grounding](https://dev.meta.ai/docs/search-grounding)).
- **Muse Voice Transcribe:** detects when someone stops speaking, labels speakers, and can be primed with names
  ([speech-to-text](https://dev.meta.ai/docs/speech-to-text)).
- **Gaps:** there's **no text-to-speech**, so the voice is an open model on GPU 1. Muse Wonder's "Active Memory" isn't
  documented for the API, so our own opt-in memory store stays.

## 8. The local models, measured (2026-10-27, evening)

Both 3090s were freed for this entry (the founder's call); our earlier prototype's services are stopped, the robot untouched.
Set up by `scripts/setup-local-models.sh`; run as the user units in `deploy/`.

- **Muse Glimmer 30B** on GPU 0: llama.cpp **b11936** (official CUDA 13.4 build, digests checked), Q4_K_M with the
  perception encoder and the DFlash drafter (auto-detected as `draft-dflash`), `-c 65536 -np 2` (32,768 a slot).
  21.9 GB. A short spoken turn: **first word 1.06 s**, done 1.44 s (36 reasoning chunks at "Reasoning effort: low").
  The Day 0 gate was 0.8 s, so it's slightly over; the voice loop should start speaking on the first sentence.
- **Picture checks** (A1, A2) through Glimmer: about 860 prompt tokens for a crop, about 70 reasoning tokens,
  **2.4 to 3.5 s** a check. A staged test: the truck photo read as REAL; the same photo shown on a drawn TV read as
  PICTURE; "the wheel under the cab" picked the right one of two.
- **SAM 3.1** open weights on GPU 1: Meta's `sam3` at `f1647e8`, `sam3.1_multiplex.pt`, through the official
  `build_sam3_multiplex_video_predictor` with a one-frame session. About 6 GB. **0.27 to 0.34 s a frame** (1800×1200).
  "wheel": 4 found, scores 0.95; "truck": 0.875; "glasses", "person": none (correct).
  - Two things that didn't work, for the record: loading the 3.1 checkpoint into `build_sam3_image_model` (the
    single-image path) gives zero detections even with all detector weights loaded; and `start_session` at this commit
    passes `offload_state_to_cpu`, which the 3.1 model's `init_state` rejects. `local/sam_server.py` registers the
    session directly.

## 9. The Reachy Mini Lite, measured (2026-10-27, evening)

The founder handed over the robot. Pollen's daemon (`reachy-mini` 1.12.0rc1, the version this repo pins as the `robot`
extra) keeps running; our code connects to it as a client, and the SDK is imported only in `robot/reachy_mini.py`.
No camera frame was saved or looked at by anyone: frames went only to local SAM 3.1 and Glimmer, and only numbers were
logged.

- **Never use `media_backend="no_media"`:** it makes the daemon *release* the camera and audio for every client (it
  happened once; `POST /api/media/acquire` gave them back).
- **The base is accurate; the head isn't.** Commanded vs reached, read back from the joints: base 40 -> 39.6; head yaw
  10 -> 4.7, 30 -> 25.3, 55 -> 40.5, 0 -> -1.8 to -5.0 (it doesn't return to the same place); pitch sags 2 to 5 degrees.
  A 6.8 degree measured turn moved a monitor 128 px, against 133 predicted by the published focal length, so the
  camera model is right and the error is the head's.
- **So the adapter is closed-loop:** the head takes at most 30 degrees and the base the rest; after a precise move it
  reads the pose back and corrects once; every frame carries the *measured* direction. Afterwards: within 1.4 degrees
  at +/-110 (mostly base), and within about 3 degrees with the head alone, inside the 6 degree pointing tolerance.
- **Speed.** A find was 14.7 s (looks 9.9 s, SAM 3.1 1.6 s, Glimmer's check 2.0 s). Sweep looks no longer correct
  themselves (the frame says where it was taken), a confident sighting (0.75+) gets its closer look at once, and the
  sweep starts in the middle: **7.5 s** for a cup, 8.2 s for a keyboard, with the TV-picture check included.

## 10. Voice, on this computer (2026-10-27, evening)

Audio from a home is as private as its pictures, so hearing and speaking run here too (`local/voice_server.py`, GPU 1).

- **Hearing: Meta's Omnilingual ASR** (Apache-2.0, open weights; facebookresearch/omnilingual-asr 0.2.0). On 30 clips
  (10 requests x 3 Kokoro voices, light noise added): CTC 1B v2 6.1% word errors, 0.024 s a clip, 2.1 GB; LLM 1B v2 5.6%,
  0.18 s, 4.8 GB; **CTC 3B v2 5.0%, 0.03 s, 6.3 GB: chosen.** Most "errors" were formatting ("3 p m"); the one real one
  in every size was "where are my" heard as "where am i", which `companion/intents.normalise` maps back, along with
  spoken times ("at three thirty p m" -> "at 3:30 pm").
  - Setup notes: fairseq2 pins torch 2.8 and NumPy 1, so torchaudio must be 2.8.0 and pyarrow below 21.
- **Speaking: Kokoro-82M** (Apache-2.0; Meta has no text-to-speech model). 4.5 s of speech made in 0.044 s once warm.
  Voice `am_michael`. Andy speaks sentence by sentence through the robot's own speaker.
- **The robot's microphone array** (16 kHz, stereo) gives a speech flag and a direction. Pollen's
  `examples/sound_doa.py`: the voice is at (sin a, cos a) in the head's frame, so 90 - a degrees left of where the head
  looks. Andy turns towards whoever says its name. Its echo cancellation is good enough that Andy's own voice, played
  from its speaker, didn't register at all (levels 0.011 to 0.023, no speech flag), so it can't answer itself.
- **Wake word:** only speech starting with "Andy" ("hey Andy") is answered; follow-ups within 20 s need no name.

## 11. Talking with Andy on the robot: what the founder's tests found (2026-10-27, evening)

Each of these came from the founder talking to the robot; the fixes are in the commits of that evening.

- **Mixed scripts:** the CTC model wrote a real voice as Arabic and Latin letters; the language-aware LLM 1B fixed it.
- **"Cup" heard as "cop"**, and a coffee mug isn't always a "cup" to SAM: names snap to the nearest everyday thing,
  and each search asks SAM for close names in the same request.
- **A false promise:** "until minutes" (for "in two minutes") left the reminder without a time; the answer to Andy's
  question then went to the chat model, which said "Got it, I'll remind you" with nothing set. Andy's questions now
  take the next answer, and code replaces any chat reply that claims an action.
- **Quiet, still and looking up:** speech raised to -21 dBFS; a 50 Hz body-language loop (breathing, listening,
  thinking, speaking with Pollen's wobbler, a found-wiggle) between moves; upward looks at a face softened to 60%,
  capped at 12 degrees.
- **Slow answers:** 8.5 s to the first word, from two blocking head turns and a tracker holding the turn. Now the head
  turns while the answer is made: **2.6 s, 1.9 s, 1.3 s** to the first word on three live turns (end of speech
  0.55 s, ASR about 0.2 s, Glimmer about 1.5 s; its reasoning can't be capped per request).
- **"Andy" buried in a long stretch:** with the room never quiet, utterances ran 15 s; the name now counts anywhere,
  stretches end at 8 s, and the microphone's detector counts only with sound behind it.
- **Privacy:** speech not for Andy is dropped and logged only as its length and the room level.
- **Streaming (later that evening):** the AI opening is said while the model thinks, and Glimmer's answer is spoken
  sentence by sentence as it's written; each sentence passes the false-promise check before it's said. First sound
  after the words are understood: **0.97 s, 0.69 s, 0.97 s** on three turns on the robot (was 1.7 to 2.8 s).

## 12. Following a thing with the eyes (2026-10-27, night)

"Andy, follow the mug": find it, then each frame SAM 3.1 (local) finds the mug, the mask nearest the last position is
taken as the same mug (so a look-alike nearby isn't swapped in), and the head eases after it through the body-language
loop; past the head's 25 degrees the base turns. "Stop" reaches it without waiting for the turn's lock. On the robot:
**about 2.4 frames a second** (22 SAM 3.1 frames, find included, over an 8 s follow).

## 13. Muse Spark and SAM 3.1 live through the Model API (2026-10-27, night)

The founder chose to use billing before the hackathon credits arrive. First calls (`scripts/smoke_model_api.py`,
about $0.02 a run; results in `evals/results/smoke-model-api-*.json`):

- **Muse Spark thinks at length by default:** 550 reasoning tokens for a one-sentence answer, so a 120-token limit
  returned nothing. `reasoning_effort`: minimal 116 tokens, 2.7 s; low 315; medium 510. Andy uses **minimal** for
  conversation (1.1 to 1.3 s) and **low** for planning searches and web answers, with room to answer.
- **Planning a search with the tools works:** "reading glasses by the TV on the right" -> look right, look closer
  (confirmed and pointed) in 2 calls, 2.4 to 5.8 s.
- **Web search answers arrive in phases:** "commentary" messages while it works ("I'll get Miami's forecast for
  tomorrow.") and a final message with `url_citation` annotations. Andy speaks only the final one. Asked to cite and to
  use US units: "mostly sunny with a high near 84 degrees Fahrenheit ... according to forecast.weather.gov", 5 to 9 s,
  so Andy says "Let me look that up" first. Not every answer comes with a citation.
- **SAM 3.1 through the API** takes a base64 data URL (open since day one): the drawn mug at 0.89, 1.4 to 3.8 s.

## 14. Looking and telling, and the memory map (2026-10-27, night)

- **"What's on the desk?"** on the robot: "On the desk there is a white keyboard and a phone resting on some papers. A
  mug and a monitor are up behind it." Glimmer on this computer; 20.7 s with the full 1080p frame, **12.2 to 12.6 s**
  with the frame shrunk to 1024 px first (Andy says "Let me see" at once). "What am I holding?" faces the person, looks
  lower, and crops around the hands SAM 3.1 finds.
- **The TV's memory map:** watched things at the direction they were last seen, nearer when lower, fading with age.
- **Muse Spark rescored after the tool fixes** (no repeat looks; compare points): TV pictures 14 -> 20/20, behind
  18 -> 20/20, look-alikes 12 -> 16/20 (one wrong point), model time 3 to 9 s a search.

## 15. One agent over all of Andy's abilities (2026-10-27, night)

Muse Spark (Glimmer offline) gets the robot's abilities as tools: find, follow, look and tell, keep an eye on,
forget, what I remember, set and list reminders, draw, look up. Each tool is the same code as the simple path, so it
moves the body, checks its arguments and speaks its own acknowledgements; the model only sees their words. On the
robot with Muse Spark: "find the cup and remind me in two minutes to drink some water" -> find (searched, pointed),
set_reminder (set): "I see your cup straight ahead! Your reminder is set for 7:45 to drink some water." in 19.8 s.
"Good morning, Andy" -> a briefing in 13.3 s. Without a home town the weather came back for three other cities, so
Andy now asks where the person lives unless `--home` / `HEYANDY_HOME` says.

## 16. What's missing, and what would be new (research, 2026-10-27, night)

A survey of products, research and needs (sources below; the robots' own claims are theirs, not tested here).

- **Products:** Samsung put Ballie on hold indefinitely (January 2026); Amazon dropped Astro for business (2024); ElliQ
  does reminders, calls and conversation but nothing with objects; of 200+ community Reachy Mini apps, none searches for
  objects and points, or is made for older adults. Moxie robots stopped working when their maker's servers shut (January
  2025), which is why Andy works offline.
- **Research gaps Andy can close:** MIT's DAAAM lists *when things moved* and *how sure the robot is* as open problems;
  FARM found people describe places by what's near them ("left of the poster"), improving search 164%; OK-Robot's top
  real-home failure was picking the wrong object from memory (9.3% of tries).
- **Needs:** 12.1% of people 65+ have trouble seeing words and letters (Census); older adults would rather a robot than a
  person handle objects and keep track of information (Smarr et al.); the camera is the main privacy worry about home
  robots; ElliQ reviewers dislike interruptions ("nagging"); in Apple's ELEGNT study older participants liked
  expressive motion less.
- **Ranked ideas:** (1) when did it move, and what's it near, in words, with how long ago; (2) "this one is mine" (a
  local reference picture); (3) several things tracked at once with SAM 3.1's Object Multiplex (a shell game); (4) read
  and act (left out: our earlier prototype has a letter reader, and medical papers slide into advice); (5) a privacy receipt on
  the TV; (6) Muse Wonder working a browser on the TV. Also: a quiet mode and calmer motion.
- **Avoid:** medical papers, safety monitoring (stove, falls), companionship framing, describing without acting, cloud
  voice outside a staged scene, claims about Glimmer fine-tuning on 24 GB or running Muse Spark Open locally, unlabelled
  sped-up footage.

Sources: androidauthority.com/samsung-ballie-robot-shelved-indefinitely-3630980 ·
engadget.com/amazon-pulls-the-plug-on-the-business-version-of-its-astro-robot-193907015.html ·
theseniorlist.com/aging-in-place/elliq · pollen-robotics.com/reachy-mini/community ·
axios.com/2024/12/10/moxie-kids-robot-shuts-down · arxiv.org/abs/2401.12202 (OK-Robot) · arxiv.org/abs/2309.16650
(ConceptGraphs) · thenextweb.com/news/mit-daaam-robot-long-term-memory-objects · arxiv.org/abs/2606.15476 (FARM) ·
access-board.gov/research/communication/variable-message-signing/influence-visual-impairments ·
pmc.ncbi.nlm.nih.gov/articles/PMC8374875 · ar5iv.labs.arxiv.org/html/2302.12686 (Smarr et al.) ·
homes.luddy.indiana.edu/selmas/CaineSabanovic-HRI2012.pdf · ncbi.nlm.nih.gov/pmc/articles/PMC10252978 ·
thomasnet.com/insights/companion-robots-for-elderly-get-mixed-reviews ·
venturebeat.com/ai/apples-elegnt-framework-could-make-home-robots-feel-less-like-machines-and-more-like-companions ·
arxiv.org/abs/2511.16719 (SAM 3) · dev.meta.ai/docs/sam/segmenting · dev.meta.ai/docs/computer-use ·
dev.meta.ai/docs/muse-glimmer/prompting · techcrunch.com/2024/02/09/how-to-fake-a-robotics-demo-for-fun-and-profit

## 17. Memory with a history, in words (2026-10-27, night)

From section 16's top idea. Each watched thing keeps its last 8 places: where (direction), when first and last seen
there, and Glimmer's few words about it, written in the background from the best view and kept as words only. A
sighting more than 10 degrees from the last place starts a new entry (it moved). On the robot: the cup found in 8.0 s;
4.0 s later its place read "on desk in front of monitor, behind keyboard"; "when did you last see the cup?" answered
from memory without the robot moving. Also built from section 16: a privacy receipt on the TV, quiet mode and calmer
motion.

## 18. Several things at once: the cup game with SAM 3.1 Object Multiplex (2026-10-27, night)

From section 16's third idea. Measured on GPU 1 (RTX 3090) with `build_sam3_multiplex_video_predictor`, before building:

- **Speed:** 5.7 frames a second on 20 real camera frames shrunk to 960x540 (one or two objects), about 5 on synthetic
  shuffles of three cups. The image encoder runs on every frame, and there's no setting to detect less often.
- **Memory:** the first tries ran out of memory on the 24 GB card. It wasn't the clip's length: sam3's builder detects 16
  frames at a time (`batched_grounding_batch_size=16`) and keeps the previous batch, about 370 MB a frame. At 4 a batch
  the peak is 10.5 GB with the model, whatever the clip's length, so it fits beside the voice server.
  `trim_past_non_cond_mem_for_eval` crashes on this model (`KeyError: 'multistep_point_inputs'`) and isn't needed.
- **bfloat16:** sam3 turns on bfloat16 autocast only for the thread that built the model, so tracking in a server
  request thread failed on a dtype mismatch until it was wrapped in autocast itself.
- **Accuracy, synthetic** (three identical red cups on a wooden table, the ball hidden under one, 4 swaps of 0.8 s each,
  the cups passing in front of and behind each other): at **10 frames a second, 4 of 4** standalone and 4 of 5 through
  the server; at **5 frames a second, 0 of 4** (lost or swapped mid-swap). Shuffles saved as upscaled JPEGs did worse
  (3 of 10, with 0.6 s swaps failing every time), which says these drawn frames aren't a fair stand-in for a camera;
  real cups still need scoring.
- **Dropped and found again:** where two cups cross, SAM 3.1 sometimes drops one and finds it a frame or two later under a
  new id. Joining a track that ends early to one starting within 6 frames near where it was heading turned 2 of the
  misses into right answers.

So Andy records the shuffle at the camera's full 10 frames a second (in memory only), watches with single frames a few
times a second for the ball to vanish and the cups to settle, then replays the clip from the moment the ball vanished.
A 4-second shuffle replays in about 9 s; Andy says "Let me replay that" and the TV shows the stage. It asks for a
shuffle "not too fast". Then it points, says "Lift it up", checks which cup the ball appears under, and keeps score for
the session.

## 19. "This one is mine": knowing the person's own things by sight (2026-10-27, night)

Section 16's second idea. "Andy, this is my mug": Andy looks at the person's hands, SAM 3.1 masks the mug in four
frames as it's turned, and each view becomes a vector; later finds compare each mug they confirm with those views and
skip one that isn't alike enough. Kept as numbers in `mine.json` (mode 600), never a picture.

- **The model:** DINOv3 would be the first choice (Meta's newest, strongest at telling instances apart), but its
  weights need a licence request on Hugging Face, so DINOv2-base (Apache-2.0, pinned revision) runs now, on GPU 1 inside
  the SAM server: 350 MB, 0.4 s for a request with its first load 1.2 s. Swapping is one line.
- **Which features** (the robot's camera, things on the founder's desk seen from four head angles, numbers only, frames
  not kept): the mask-weighted mean of DINOv2's patch tokens held up best across views (the same thing: median 0.86,
  minimum 0.47; the class token: median 0.81, minimum 0.36), so only the thing's own pixels count.
- **Colour:** DINOv2 learned to ignore colour (it was trained with colour jitter): a blue and a red mug of one shape
  scored **0.94** alike. Half of the likeness is now a colour fingerprint (12 hues by 3 strengths, and 4 greys, over the
  masked pixels, compared by overlap). Drawn mugs: the same blue one in dimmer light or moved 1.00; red 0.55; white
  0.62; a blue cup of another shape 0.81.
- **On the robot, combined** (five head angles, every thing SAM 3.1 found): the same thing from another angle scored
  **0.79 to 0.98** (median 0.89); different things median 0.39 (the highest 0.94 were near-identical pieces of one
  monitor and keyboard). The threshold is 0.75.
- **Limits:** two mugs of the same colour and a similar shape will look alike; held in the hand under one light and
  found on a table under another hasn't been measured yet. The TV shows each mug's likeness ("a mug, 82% like yours")
  so the founder's tests can set the threshold.

## 20. Using the web on the TV: Meta's computer use (2026-10-27, night)

Section 16's sixth idea, from [dev.meta.ai/docs/computer-use](https://dev.meta.ai/docs/computer-use): the Responses
API's `computer` tool; each `computer_call` carries a batch of `actions`, and the client answers with a screenshot.

- **Muse Wonder** refuses the tool on our account (`400 Unsupported tool type: 'computer'`; plain Wonder chat works), so
  **Muse Spark 1.3** runs the loop, as the docs allow.
- **Every batch comes with a safety check** (`computer_action_requires_confirmation`, "Review and confirm before
  executing this computer action"), even typing a search. So the review is ours, in code, before anything runs:
  nothing that looks like an email address, a phone or card number or a password is typed; unexpected key
  combinations are refused; a page whose address is a sign-in, account, checkout or payment page ends the run (and a
  click that lands on one goes back). Only then is the check acknowledged.
- **The headless browser has no address bar**, so "ctrl+l, type, Enter" is caught and done by our code. DuckDuckGo
  turns a headless browser away; Bing answers one that says it's Chrome.
- **Speed:** each model turn took 10 to 15 s. Clicking through search results took 1.5 to 4 minutes for a recipe
  (9 to 15 steps). Letting Muse Spark's web search pick the page first (4 to 8 s) and opening it directly put it on the
  TV in **6 to 11 s**, with Andy's sentence about it at **10 to 16 s** (recipe 10.4 s, radar 11.1 s, Northern Lights
  pictures 13.8 s; through Andy's turn, the radar in 15.6 s). Computer use then has at most 3 steps or 45 s to bring
  the answer into view; follow-ups ("scroll down") at most 2 steps or 40 s. "Zoom in on the map" failed (98 s before the
  limits), and a question like opening hours is better answered in words (Andy's web answers), not on a page.
- **The follow-up quirk:** a screenshot can be sent as an input image only in a run's first request ("native computer
  input images are supported only in the initial request"), so follow-ups send words and the model asks for a
  screenshot.
