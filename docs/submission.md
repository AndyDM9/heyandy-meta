# Submission text (draft, for the form on November 4)

*About 1,200 words with the table. Fill in the [brackets] on the day; check every number against `evals/results/` first.*

---

**Andy: a tabletop robot that finds what you've lost, points at it, and keeps your private life private.**

HeyAndy, Inc. · Startup track · *Push the Frontier* (robotics) · Video: [link] · Live screen: huggingface.co/spaces/heyandy-ai/andy · Code: github.com/AndyDM9/heyandy-meta

**Before this week:** a Reachy Mini Lite robot, and our own earlier object-finding prototype (none of its code is in
this repository). **Everything below was built this week, on Meta's models.**

## The problem

People who live at home lose the same few things every day: glasses, keys, the phone, the remote. A phone app can't look
for them, and a camera that streams the living room to the cloud is a camera most people won't have. Andy sits on the
table, looks around the room for you, points at the thing, and keeps what it sees and hears in the house.

## What it does, in the room

- **"Andy, where are my glasses?"** Andy turns to your voice, sweeps the room with its head (and base), looks closer, and
  points; the TV shows the picture it saw them in, with SAM 3.1's outline. A picture of glasses on the TV is skipped;
  "the blue mug, next to the laptop" picks the right look-alike; "behind you, on the left" goes straight there.
- **"Keep an eye on my keys."** Andy remembers where your chosen things were last seen, in words ("on the desk, behind
  the keyboard"), and when they moved. Never a picture.
- **"Remind me at 3 pm to call Sam."** At the time, Andy finds you with its camera, turns to you, and says it.
- **"Andy, I'm going out."** Andy looks where it last saw your things and points at any still here ("Don't forget your
  keys"), while Muse Spark checks whether you'll need an umbrella.
- **"Andy, this is my mug."** Andy learns your mug by sight as you turn it, then "where's my mug?" skips anyone else's.
  It keeps a few thousand numbers, never a picture.
- **"Andy, what's that?"** while pointing: Andy looks where you point, finds it, points at it too: "You mean the lamp?"
- **"Andy, let's play the cup game."** Andy records the shuffle, replays it through SAM 3.1 Object Multiplex (every cup
  tracked at once), and points at the cup with the ball. The TV draws each cup's path.
- **"Show me the weather radar on the TV."** Muse Spark picks the page; its computer use brings the radar into view in a
  clean browser, each step on the TV.
- **"Draw me a lighthouse at dawn"**, **"draw me a map of my things"** (Muse Image, from words only), questions about
  the world with their sources, conversation, and **"habla español"**: Andy hears, speaks and shows the TV in Spanish.
- **Several things at once:** "find my glasses, then my keys, then remind me in an hour to leave" goes to an agent with
  all of Andy's abilities as tools (Muse Spark, or Glimmer offline).

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; says what it sees; translates Spanish |
| **Omnilingual ASR** (open weights) | GPU 1 | Hears the person, in English or Spanish |
| **DINOv2** (open weights) | GPU 1 | Knows the person's own things by sight |
| **Llama Prompt Guard 2** (open weights) | GPU 1 | Reads each web page first: one that tries to instruct Andy ends the run |
| **Llama Guard 3 8B** (open weights, 4-bit, converted here) | GPU 1 | A second crisis check on what the person says, before any other model |
| **Muse Spark 1.3** (Model API) | Cloud: words, and screenshots of web pages you ask to see | Plans searches and multi-part requests; web answers with sources; computer use |
| **Muse Image 1.0** (Model API) | Cloud: words only | Pictures and the map of your things |
| *(not Meta)* Kokoro-82M | GPU 1 | Andy's voice |

**Pictures and voice from a home never leave it.** Meta can't turn off data retention for hackathon credits, so the
camera and microphone reach only models on the computer beside the robot. Every turn, the TV shows a privacy receipt:
exactly which words went to which cloud model, or "Nothing left this house". "Andy, what did you send to the cloud
today?" adds up the day's receipts, on this computer. Unplug the network and Andy carries on.

## Technical depth (what was hard)

- **A closed-loop head.** The robot's head falls short and sags (asked for 55 degrees, it reached 40.5); the adapter
  reads the pose back, corrects once, and every frame carries the measured direction: pointing within about 3 degrees.
- **Agents that can't move the robot by themselves:** named views and numbered places, never motor values; every
  argument checked in code; Andy's words built from the tools' results, never the model's.
- **Identical cups, crossing.** Object Multiplex tracks about 4 frames a second on a 3090; at 5 frames a second of
  video the cups were lost every time, so Andy records at 10 and replays. Small detection batches fit it on one 24 GB
  card beside the voice, Prompt Guard and Llama Guard.
- **Telling my mug from yours.** DINOv2 ignores colour (a blue and a red mug of one shape: 0.94 alike), so half the
  likeness is a colour fingerprint of the mug's own pixels: red 0.55, the same thing from other angles 0.79 to 0.98.
- **Straight to the answer.** Glimmer reasons privately before every answer, whatever its setting. Starting its reply
  past the reasoning made its picture checks 1.1 s instead of 1.9 (same 10 of 10 on public photos), a find on the robot
  7.1 s instead of 8.5, and Spanish translation 0.4 s a sentence, on this computer.
- **Computer use with a reviewer.** Every batch of actions is reviewed in code before Meta's safety check is
  acknowledged: nothing personal is typed, sign-in and payment pages end the run, the browser can't reach the home
  network, and Llama Prompt Guard 2 reads each page first (hidden "ignore your instructions" text: stopped in 0.06 s).

## Measured

*Search, simulated* (the robot's camera model, seeded rooms): with look-alikes described, the fixed sweep pointed at the
wrong one 20 times in 100; **Glimmer's plan 17 of 20, 1 wrong** (Muse Spark 16 of 20, 1 wrong). Things behind the robot:
**20 of 20 in 3.9 looks** (Spark 3.2; fixed sweep 92 of 100 in 6.2). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12** (6 of 12 before the fixes
this scorecard showed were needed), **Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every request the program made recorded on its way
out): **no camera picture reached the cloud** (21 taken), **every word sent was on its turn's receipt**, crisis words
reached no model; offline, nothing at all went.
*Spanish:* **40 of 41** written requests and **37 of 41** spoken ones reach the right ability.
*On the robot:* a cup found in 7.5 s and a keyboard in 7.1 s; first word 0.7 to 1 s after Andy understands you;
[the physical scorecard: N of M].
*Not yet tried on the robot with real things or a person:* the cup game (synthetic shuffles: 4 of 5), my mug, "what's
that?" (public photos: 4 of 6), going out (robot simulated). Every result, failures included: `evals/results/`.

## Safety and honesty

Andy says it's an AI at the start of a conversation and every three hours; crisis words, in English or Spanish, get
the 988 line in code and reach no other model, checked twice on this computer (a word list, then Llama Guard 3, which
caught 3 of 8 phrasings the list missed, with no false alarms on 12 ordinary ones, in 0.04 s); no medical advice; it
never asks for money or passwords. Speech that isn't for Andy is dropped and never shown or kept. Model API spend has a
hard cap.

## What's next

Our own robot body (in design), the same software behind the same body interface; more languages; and the physical
scorecard in more homes.
