# HeyAndy x Meta

**A tabletop robot that finds what you've lost, and points at it.** It's built on Meta's models for people who live at
home, starting with older adults. Entered in Meta's Global AI Developer Hackathon (startup track, *Push the Frontier*) by
**HeyAndy, Inc.**, a Delaware corporation ([heyandy.ai](https://heyandy.ai)). HEYANDY™ is the subject of a pending US
trademark application.

## What it does
1. **Ask "where are my glasses?"** The robot looks around the room.
2. **SAM 3.1 finds them.** Its mask becomes the head's angle. The robot looks closer, checks, and points.
3. **The TV shows the picture it saw them in,** with the mask drawn. The picture is kept in memory only, never saved.
4. **Muse Spark plans the search; Muse Glimmer works offline.** Muse Spark plans through the Meta Model API. Muse Glimmer
   runs on the computer beside the robot, so the robot keeps working with no internet.
5. **"The blue mug next to the laptop."** When there are look-alikes, Glimmer compares them and picks the one you
   described. A picture of your glasses on the TV isn't mistaken for your glasses.
6. **"Andy, follow the mug."** Andy keeps its eyes on a thing as you move it around: SAM 3.1 finds it about twice a
   second on the computer beside the robot, and past the head's reach the base turns. Say "stop" when you're done.
7. **"Andy, I'm going out."** Andy looks again where it last saw the things you asked it to keep an eye on, turns and
   points at any still here ("Your keys are still here, on the desk"), says which it didn't see (so they're probably
   with you), reminds you of the next reminder, and, looked up by Muse Spark while the robot was checking, whether to
   take an umbrella. About 7 s; the TV shows the checklist.
8. **"Andy, let's play the cup game."** Hide a ball under one of a few cups and shuffle them. Andy records the
   shuffle, then replays it through SAM 3.1's Object Multiplex on the computer beside the robot, which tracks every
   cup at once, so identical cups keep their own identities as they cross. Andy points at the cup with the ball, the TV
   draws each cup's path, and Andy watches the reveal and keeps score.
9. **"Andy, this is my mug."** Hold it up and turn it; Andy learns it by sight. Later, "where's my mug?" skips
   anyone else's. What it looks like is kept as numbers on the computer beside the robot (DINOv2, Meta's open image
   model, plus a colour fingerprint, over SAM 3.1's mask of the mug alone), never a picture. "Forget my mug" deletes it.
10. **"Andy, show me the weather radar on the TV."** Muse Spark's web search picks the page, a clean browser on the
   computer beside the robot opens it (no sign-ins, no downloads), and Muse Spark's computer use brings what was asked
   into view; the TV shows each step, with a dot where Andy clicks. "Scroll down", "go back". Code reviews every action
   before it runs: nothing personal is typed, and a sign-in or payment page ends it. Screenshots of web pages go to the
   cloud; the camera never does, and the TV's privacy receipt says which went.
11. **"Andy, draw me a lighthouse at dawn."** Muse Image makes the picture from your words; it shows on the TV and is
   saved to your Pictures folder to print or share. "Make it sunset" changes it. **"Draw me a map of my things"** paints
   where the things Andy keeps an eye on were last seen, from words only (what each is near, and which way), labelled
   large: a drawing from memory, not a photo.
12. **"Andy, what am I holding?" / "What's on the table?"** Andy looks (at your hands, found with SAM 3.1, or down
   at the table) and Glimmer says what it sees, on the computer beside the robot.
13. **"Find my glasses, and remind me at 5 to clean them."** More than one thing at once goes to an agent: Muse Spark
   (or Glimmer, offline) gets all of Andy's abilities as tools (find, follow, look and tell, keep an eye on, reminders,
   pictures, look up) and does them in order. **"Good morning, Andy"** (the first of the day) gets a short briefing:
   the weather where you live, today's reminders, and where your things are.
14. **"Speak up", "speak more slowly", "say that again."** How Andy speaks is set by voice and remembered.
15. **Talk to it.** "Andy, where are my glasses?" Andy turns towards your voice, then looks. Hearing (Meta's
   Omnilingual ASR) and speaking (Kokoro) run on the computer beside the robot.
16. **Pictures from your home never leave it.** SAM 3.1 (open weights) and Glimmer see the camera on the computer beside
   the robot, and so do your voice and Andy's. Muse Spark in the cloud only ever gets words: labels, directions and plan
   steps.

## Built during the event, and what came before
**This repository was started after the kickoff** (October 26, 2026, 12 PM ET) and holds only work done during the event.

**What existed before:**
- **our earlier prototype** ([(not in this repository)](https://(not in this repository))): the founder's
  earlier robot, built before this event. Its finder uses a vision-language model. It is **not in this repository,
  and nothing here imports it.** Its published results are our *baseline*: we run it unchanged in its own repository and
  bring only its result files here, marked as pre-existing.
- **Third-party open source**, used under its licences: Pollen Robotics' Reachy Mini SDK, simulation scene and published
  camera calibration; llama.cpp; Meta's `meta-sam-parser`.

**What's new here,** all built during the event (the day-by-day record: [docs/build-plan.md](docs/build-plan.md) and
[docs/research.md](docs/research.md)):
- **On the Reachy Mini Lite:** a closed-loop adapter (the only module that imports Pollen's SDK). The head falls short and
  sags, so it reads the pose back, corrects once, and every frame carries the measured direction; the base turns past
  the head's reach. Body language in a 50 Hz loop: breathing, listening, thinking, moving with its own words, a
  found-wiggle; it keeps its eyes on the person.
- **Meta's open weights on our own hardware:** SAM 3.1 served locally (several things per frame), Muse Glimmer on
  llama.cpp, Omnilingual ASR; with `scripts/verify_open_weights.py` proving the served Glimmer file is Meta's.
- **The search:** SAM 3.1 masks become head angles; a sweep (middle first), an early closer look at a confident
  sighting, a confirmed centred look before any point; Glimmer's picture check skips a thing on a TV or in a photo;
  close names in one request ("cup" also finds the mug).
- **Agents that plan the search with the robot's tools:** Muse Spark online, Muse Glimmer on this computer, with the
  same checked tools (named views and numbered places, never motor values), ten looks at most, no repeat looks, and
  Andy's words written from the tools' results, never the model's.
- **Following:** "Andy, follow the mug": the eyes follow it as it's moved, about 2.4 frames a second.
- **Memory with a history, in words:** an opt-in idle glance notes where chosen things are; Glimmer describes each new
  place by what's near it ("on the desk in front of the monitor, behind the keyboard"), and Andy notes when a thing
  moved. "When did you last see my keys?" is answered from memory without moving. Never a picture.
- **Voice on this computer:** Omnilingual ASR and Kokoro, the robot's microphone array (and the voice's direction),
  "Andy" as the wake word with its common mishearings, answers spoken sentence by sentence: the first word about a
  second after Andy understands.
- **Reminders delivered in person,** with Andy's questions taking the next answer.
- **Muse Spark** for web answers with their sources (US units, only the final answer spoken) and harder conversation;
  **Muse Image** for pictures from the person's words, shown on the TV and saved.
- **Safety in code:** "I'm an AI" at the start and every three hours; a crisis reply with the 988 line before any model
  sees the words ([docs/crisis-protocol.md](docs/crisis-protocol.md)); no false promises (a chat reply that claims an
  action is replaced); speech not for Andy is dropped; a hard cap on Model API spend.
- **The TV page,** read-only and on this computer, and the same page as a Hugging Face Space on sample data.
- **Scorecards:** a simulated one (fixed sweep, Glimmer and Spark planners, seeded rooms) and a physical one.

## Run it
```bash
uv sync --extra dev && uv run pytest -q   # no network calls: the model clients are tested against stand-ins
uv run python -m heyandy_meta             # talk to Andy by keyboard, in a pretend living room; TV at 127.0.0.1:8765
```
The models on this computer (Glimmer on GPU 0, SAM 3.1 on GPU 1, two 24 GB cards) are set up by
`scripts/setup-local-models.sh` and run as the user services in `deploy/`. Muse Spark is used when `MODEL_API_KEY` is set
and `HEYANDY_PAID_CALLS=1`; spend stops at a hard cap of $140.

## Layout
```
heyandy_meta/app.py        one turn: what was asked, what the robot does and says; `python -m heyandy_meta` runs it
heyandy_meta/companion/    request rules, reminders, facing the person, answers with sources, AI disclosure, crisis protocol
heyandy_meta/finder/       the search, from a SAM 3.1 mask to where the head looks; Glimmer's picture checks; names
heyandy_meta/agent/        the search tools and the planning loop (Muse Spark online, Muse Glimmer on this computer)
heyandy_meta/memory/       where watched things were last seen, and the idle glance
heyandy_meta/voice/        listening for "Andy", cutting speech into turns, Andy's voice
heyandy_meta/robot/        the body interface, the Reachy Mini adapter (the only Pollen SDK import), body language,
                           and a simulated room for tests
heyandy_meta/screen/       the TV page
heyandy_meta/models/       the model clients: Muse Spark (Model API), Muse Glimmer, SAM 3.1 (both on this computer)
heyandy_meta/router.py     who answers a turn: the device or the cloud
heyandy_meta/network.py    whether the cloud is reachable right now
heyandy_meta/budget.py     the hard cap on Model API spend
local/                     SAM 3.1, and hearing and speaking, served on 127.0.0.1 only
evals/                     the simulated and physical scorecards, and their results
scripts/, deploy/          setting up and running the models and Andy on this computer; the screen on sample data
config/                    config.example.yaml (no secrets)
docs/                      the build plan, the hackathon's rules, research, the video plan, open weights
tests/
```

## The screen beside Andy

A TV or monitor beside the robot shows, in large type read from across a room:
- **the day and time;**
- **what Andy is doing, and what its head is turned to** ("Pointing · At your mug");
- **the next reminder,** with how long until it;
- **what Andy keeps an eye on,** with where and when each was last seen;
- **what Andy found:** the picture it saw it in, with SAM 3.1's outline (kept in memory for two minutes, never saved);
  the plan step by step; the time it took;
- **answers with their sources;**
- **which Meta models worked on this turn,** on this computer or in the cloud (words only);
- **a privacy receipt:** exactly which words went to which cloud model this turn, or "✓ Nothing left this house";
- **captions of Andy's words** (never the person's).

"Andy, what can I ask?" opens a guide. Frosted panels over colour that follows the time of day, a calm night mode, every
text colour at least 7:1 against its panel (tested), and the Atkinson Hyperlegible typeface (made for low vision) served
by Andy itself: the TV asks nothing of anyone outside the house.

![Found: the picture with the mug outlined, the plan, the time and the models used](docs/images/tv-found.png)

| | |
|---|---|
| ![Finding](docs/images/tv-finding.png) | ![An answer with sources](docs/images/tv-answer.png) |
| ![At night](docs/images/tv-found-night.png) | ![What can I ask?](docs/images/tv-help.png) |
| ![A picture from your words, by Muse Image](docs/images/tv-drawing.png) | ![What Andy remembers](docs/images/tv-memory.png) |

**Try it in your browser:** [huggingface.co/spaces/heyandy-ai/andy](https://huggingface.co/spaces/heyandy-ai/andy), the
same page on sample data (pick a scene at the top). Or locally, with no robot: `uv run python scripts/demo_screen.py
--cycle`, then open http://127.0.0.1:8765. The picture in these is drawn by the script, not taken in a home.

## Measured so far

**Simulated scorecard** (`evals/sim.py`, seeded rooms; the camera model is the robot's, robot time is estimated from what
was measured on it, and the noise is stated in the results). The fixed sweep runs on every plain request; an agent plans
the search when the person gives a hint: Muse Glimmer on this computer, or Muse Spark through the Model API.

| Room | Fixed sweep (100 each) | Glimmer plans (20 each) | Muse Spark plans (20 each) |
|---|---|---|---|
| The thing in front | 96 found, 0 wrong | 19, 0 wrong | 19, 0 wrong |
| Behind the robot, with a hint | 92, 0 wrong, 6.2 looks | **20**, 0 wrong, 3.9 looks | **20**, 0 wrong, 3.2 looks |
| A picture of it on the TV too | 94, 0 wrong | 19, 0 wrong | **20**, 0 wrong |
| Not there at all | 100 said so | 20 said so | 20 said so |
| Two look-alikes, "the blue one" | 80, **20 wrong** | 17, 1 wrong | 16, 1 wrong |
| Planning time (model only) | none | 7 to 24 s | **3 to 9 s** |

Pointing error (median, with 1.5 degrees of assumed head noise): about 1.7 degrees, inside the 6 degree target. The
agents' scores are after the tool fixes of October 27 (no repeat looks; compare points at once); before them, Spark found
only 12 look-alikes and 14 TV cases (`evals/results/*-before-tool-fixes.json`). Glimmer's times in this run were slowed by
the robot sharing its GPU; with 20 rooms a scenario, a few points either way is noise. Results: `evals/results/`.

**On the robot** (Reachy Mini Lite, 2026-10-27): a cup found in 7.5 s and a keyboard in 8.2 s, the screen check included;
pointing within about 3 degrees after the head's correction.

**The cup game, tracking only** (SAM 3.1 Object Multiplex on an RTX 3090, synthetic shuffles of three identical cups, 4
swaps of 0.8 s each; `docs/research.md` section 18): about 5 frames a second, so a 4-second shuffle replays in about 9 s.
At the camera's 10 frames a second it picked the right cup in 4 of 5 runs; at 5 frames a second it lost the cups in all 4. Not
yet scored with real cups. The physical scorecard (`evals/physical.py`) comes next.

## What doesn't work yet
- **The cup game hasn't been scored with real cups yet.** Its tracking was measured on synthetic shuffles (above);
  identical cups crossing fast can still swap.
- **The Model API sometimes returns `404 model_not_found` on new accounts** (reported by other participants; Meta is
  investigating). Calls retry twice, then the robot answers on the device.
- **The physical scorecard isn't done yet.** On the robot Andy has found real things, delivered a reminder in person,
  and held conversations (first word 0.7 to 1 s after it understands); the scored runs come next
  (`docs/research.md` sections 8 to 11).
- **English only** for now: Omnilingual ASR can hear far more languages, but Kokoro speaks English here.

## Licence
Apache-2.0. `meta-sam-parser`, a dependency, is under Meta's SAM License.
