# Submission text (draft, for the form on November 4)

*About 1,000 words. Fill in the [brackets] on the day; check every number against `evals/results/` first.*

---

**Andy: a tabletop robot that finds what you've lost, points at it, and keeps your private life private.**

HeyAndy, Inc. · Startup track · *Push the Frontier* (robotics) · Video: [link] · Live screen: huggingface.co/spaces/heyandy-ai/andy · Code: github.com/AndyDM9/heyandy-meta

**Before this week:** a Reachy Mini Lite robot, and our earlier prototype, our earlier robot built before this event (not in this
repository; its results are our baseline). **Everything below was built this week, on Meta's models.**

## The problem

People who live at home lose the same few things every day: glasses, keys, the phone, the remote. A phone app can't look
for them; a camera that streams the living room to the cloud is a camera most people won't have. Andy is a small robot
that sits on the table, looks around the room for you, points at the thing, and keeps everything it sees and hears in
the house.

## What it does, in the room

- **"Andy, where are my glasses?"** Andy turns towards your voice, says "Let me look", sweeps the room with its head
  (and its base, past the head's reach), looks closer at the likeliest place, and points. The TV beside it shows the
  picture it saw them in, with SAM 3.1's outline.
- **It isn't fooled by pictures.** A pair of glasses on the TV screen or in a photo is checked and skipped.
- **"The blue mug, next to the laptop."** With look-alikes in view, Andy compares them and points at the one you meant.
- **"I left my keys behind you, on the left."** With a hint, an agent plans the search with the robot's tools and goes
  straight there.
- **"Andy, follow the mug."** Its eyes follow a thing as you move it around the table, until you say "stop".
- **"Keep an eye on my keys."** While idle, Andy glances around now and then and remembers where the things you chose
  were last seen, and when they moved, described in words by what's near them ("on the desk, behind the keyboard"):
  never a picture. "When did you last see my keys?" is answered from memory: "40 minutes ago, on the desk behind the
  keyboard; before that by the door, until 3:12." Remembering *when things moved* is an open problem in robot memory
  research (MIT's DAAAM).
- **"Remind me at 3 pm to call Sam."** At the time, Andy finds you with its camera, turns to you, and says it in your
  own words. If you're out, it tries again and tells you later.
- **"Andy, what am I holding?" / "What's on the table?"** Andy looks at your hands (found with SAM 3.1) or down at
  the table, and Glimmer says what it sees, all on the computer beside the robot.
- **"Andy, I'm going out."** Andy looks again where it last saw your keys, wallet and glasses, and points at any still
  here: "Don't forget your keys." Meanwhile Muse Spark looks up whether you'll need an umbrella. About 7 seconds, both
  at once; the TV shows the checklist.
- **"Andy, habla español."** Andy hears and speaks Spanish, the first language of many people in South Florida.
  Omnilingual ASR is told to hear Spanish, and Muse Glimmer translates between the person and Andy's English rules on
  the computer beside the robot, in half a second, so every ability works in Spanish and nothing leaves the house for
  it. The AI disclosure and the crisis reply are written by hand.
- **"Andy, let's play the cup game."** Hide a ball under a cup and shuffle. Andy records the shuffle, replays it
  through SAM 3.1's Object Multiplex (every cup tracked at once, on the computer beside the robot), points at the cup
  with the ball, and keeps score. The TV draws each cup's path through the shuffle.
- **"Andy, this is my mug."** Andy learns your mug by sight as you turn it in your hands, and from then on "where's
  my mug?" skips anyone else's. What it looks like is kept as a few hundred numbers on the computer beside the robot,
  never a picture.
- **"Andy, show me the weather radar on the TV."** Andy picks the page with Muse Spark's web search and opens it in a
  clean browser; Muse Spark's computer use clicks and scrolls until the radar (or the recipe, or the pictures) is in
  view, while the TV shows each step. Every action is reviewed in code first: nothing personal is typed, and a sign-in
  or payment page ends the run.
- **"Andy, draw me a map of my things."** Muse Image paints where the things Andy keeps an eye on were last seen, with
  large labels, from words only ("KEYS on the desk, next to the lamp, to the robot's left"): a drawing from memory, not a
  photo, and the privacy receipt shows exactly those words.
- **"Andy, draw me a lighthouse at dawn."** Muse Image paints it from the person's words; it fills the TV and is
  saved to print or share; "make it sunset" changes it.
- **Questions about the world** are answered in a sentence or two with web search, naming the source aloud and listing
  the links on the TV. **Conversation** follows on without repeating its name.
- **More than one thing at once:** "Find my glasses, and remind me at 5 to clean them." An agent (Muse Spark, or
  Glimmer offline) gets all of Andy's abilities as tools and does them in order; the robot moves, the reminder is
  set, and Andy says what was done. **"Good morning, Andy"** gets a short briefing: the weather, today's reminders,
  and where your things are.
- **It's never frozen:** it breathes, its antennas listen and think, its head moves with its words, and it keeps its
  eyes on you while it talks.

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights, `sam3.1_multiplex.pt`) | GPU 1, on the computer beside the robot | Finds things in camera frames (several per frame for the idle glance), finds the person for reminders, follows a moving thing; **Object Multiplex tracks every cup at once** in the cup game |
| **Muse Glimmer 30B** (open weights, Q4_K_M + perception encoder + DFlash drafter) | GPU 0, llama.cpp | Conversation; translating to and from Spanish; **plans searches with the robot's tools** when there's a hint; checks pictures (real thing or a picture on a screen? which look-alike?) |
| **Omnilingual ASR** (open weights, LLM 1B v2) | GPU 1 | Hears the person, told the language (English or Spanish) |
| **DINOv2** (open weights, base) | GPU 1 | Knows the person's own things by sight, from SAM 3.1's mask of the thing alone, kept as numbers |
| **Muse Spark 1.3** (Model API) | The cloud, **words only** (and, for "show me … on the TV", screenshots of web pages) | Plans hinted searches when online; web answers with sources; harder conversation; **computer use** in a clean browser on the TV |
| **Muse Image 1.0** (Model API) | The cloud, **words only** | Pictures from the person's words, refined over turns |
| *(not Meta)* Kokoro-82M | GPU 1 | Andy's voice; Meta has no open text-to-speech model |

**Pictures and voice from a home never leave it.** Meta can't turn off data retention for hackathon credits (Meta's
answer in office hours), so the camera and microphone only ever reach models on the computer beside the robot; Muse
Spark gets words. Unplug the network and Andy carries on: the TV says "Offline", Glimmer plans and talks, SAM 3.1 sees.
Every turn, the TV lists which models worked on it and where.

## Technical depth (what was hard)

- **A closed-loop head.** Measured on the robot, the base turns where it's told (39.6 for 40 degrees) but the head falls
  short and sags (asked for 55, it reached 40.5). The adapter gives the head small turns, reads the pose back, corrects
  once, and every frame carries the *measured* direction: pointing within about 3 degrees.
- **SAM 3.1 served locally** with Meta's `sam3` code (two quirks in it worked around and documented), about 0.3 s a
  frame; several things per frame share one encoding.
- **Agents that can't move the robot by themselves.** Muse Spark and Glimmer plan with named views and numbered places,
  never motor values; every argument is checked in code; a search stops at ten looks; and Andy's words about what it
  found are written from the tools' results, never the model's (Glimmer once invented "on the floor").
- **Speech that's fast enough to talk to:** Omnilingual ASR and Kokoro on GPU 1, the robot's microphone array for the
  voice's direction, answers spoken sentence by sentence as Glimmer writes them: the first word [0.7 to 1 s] after Andy
  understands you.
- **Identical cups, crossing.** SAM 3.1 Object Multiplex runs at about 5 frames a second on a 3090, half the camera's
  rate, and at 5 frames a second the cups were lost every time. So Andy records at 10 and replays. The model's default
  detection batch needed about 12 GB more than the GPU had beside the voice models; 4 frames a batch keeps tracking at
  10.5 GB. Cups dropped while crossing and found again under a new id are joined back up by where they were heading.
- **Telling my mug from yours.** DINOv2 learned to ignore colour, so a blue and a red mug of one shape scored 0.94
  alike. Half of the likeness is now a colour fingerprint of the mug's own pixels: the red one scores 0.55, while the same
  thing seen from other angles on the robot scored 0.79 to 0.98.
- **Computer use with a reviewer.** Meta's computer use asks for confirmation on every batch of actions, so our code
  reviews each batch before acknowledging it: no personal details typed, and a sign-in or payment page ends the run.
  Clicking through search results took minutes (each model turn 10 to 15 s); letting Muse Spark's web search pick the
  page first puts it on the TV in 6 to 11 s.
- **Translation in half a second on a reasoning model.** Glimmer reasons privately before every answer (about 2 s,
  and sometimes all of its tokens, even for "Let me look"), whatever its reasoning setting. Starting its reply at the
  answer itself (" to=user"), past the reasoning, brings a sentence to 0.25 to 0.6 s. Two worked examples stop it copying
  Spanish back unchanged, and Andy's short phrases are written by hand ("Let me look" had come back as "look at me").
- **Never a false promise:** a chat model can't claim to set a reminder or watch something; code checks every sentence
  before it's said.

## Measured

*Simulated scorecard (seeded rooms with the robot's camera model and measured timings; noise stated):* with look-alikes
described, the fixed sweep pointed at the wrong one 20 times in 100; **Glimmer's plan: 20 of 20, none wrong**. Things
behind the robot: **20 of 20 in 3.5 looks** (fixed sweep: 92 of 100 in 6.2). Nothing there: no false finds.
*In Spanish:* 40 of 41 written requests and 37 of 41 spoken ones reach the right ability (median 0.44 s to
translate, on the computer beside the robot). *On the robot:* a cup in 7.5 s and a keyboard in 8.2 s, the screen check included; [the physical scorecard: N of M].
Every result, failures included: `evals/results/`.

## Safety and honesty

Andy says it's an AI at the start of a conversation and every three hours; crisis words get the 988 line and nothing
from a model; no medical or medication advice; it never asks for money or passwords. Speech that isn't for Andy is
dropped and never shown or kept. The Model API spend has a hard cap in code.

## What's next

Our own robot body (in design), the same software behind the same body interface; more languages (Omnilingual ASR
already hears them); and the physical scorecard in more homes.
