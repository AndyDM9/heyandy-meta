# Submission text (for the form on November 4)

*About 1,350 words with the table. Fill in the [brackets] on the day; check every number against `evals/results/` first
(every scorecard line is from the final run on October 30).*

---

**Andy: a tabletop robot that finds what you've lost, points at it, and keeps your private life private.**

HeyAndy, Inc. · Startup track · *Push the Frontier* (robotics) · Video: [link] · Live screen: huggingface.co/spaces/heyandy-ai/andy · Code: github.com/AndyDM9/heyandy-meta

**Before this week:** a Reachy Mini Lite robot, and our own earlier object-finding prototype (none of its code is in
this repository). **Everything below was built this week, on Meta's models. Every model Andy runs is Meta's.**

## The problem

People who live at home lose the same few things every day: glasses, keys, the phone, the remote. A phone app can't look
for them, and a camera that streams the living room to the cloud is a camera most people won't have. Andy sits on the
table, looks around the room for you, points at the thing, and keeps what it sees and hears in the house.

## What it does

- **"Andy, where are my glasses?"** Andy turns to your voice and looks around; the TV shows each view live, every
  candidate outlined by SAM 3.1. It points, checks with its own camera that the point landed, and says "There they
  are! On the armchair, to my left, about 5 feet away" (MapAnything, Meta's 3D model, measures how far). It skips a
  picture of glasses on the TV, picks "the blue mug, next to the laptop" from look-alikes, and goes straight "behind
  you, on the left".
- **"Keep an eye on my keys."** Andy remembers where your chosen things were last seen, in words ("on the desk, behind
  the keyboard") and how far, and the TV draws a floor plan. Never a picture.
- **"Remind me at 3 pm to call Sam."** At the time, Andy finds you with its camera, turns to you, and says it.
- **"Andy, I'm going out."** Andy points at what's still here ("Don't forget your keys") while Muse Spark checks
  whether you'll need an umbrella.
- **"This is my mug"** (Andy learns it by sight, as numbers, and skips anyone else's); **"what's that?"** (Andy looks
  where you point and points at it too); **the cup game** (SAM 3.1 Object Multiplex tracks every cup at once through
  the shuffle). These three and "going out" are built and measured in simulation or on photos, not yet on the robot
  with real things (see Measured).
- **"Show me the weather radar on the TV"** (Muse Spark's computer use), **"draw me a map of my things"** (Muse Image,
  from words only), answers with sources, conversation, **Spanish**, and several things at once through an agent with
  Andy's abilities as tools (Muse Spark, or Glimmer offline). At calm moments Andy shows a feeling with one of Pollen's
  recorded moves: a thank-you, a good morning, an oops.

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; says what it sees; translates Spanish |
| **MapAnything** (open weights) | GPU 1 | How far away a found thing is, from one frame; the floor plan |
| **Omnilingual ASR** (open weights) | GPU 1 | Hears the person, in English or Spanish |
| **SeamlessM4T v2** (open weights, its speech half) | GPU 0 | Andy's voice, English and Spanish |
| **DINOv2** (open weights) | GPU 1 | Knows the person's own things by sight |
| **Llama Guard 3 8B**, **Llama Prompt Guard 2** (open weights) | GPU 1 | A second crisis check before any other model; reads each web page before Muse Spark does |
| **Muse Spark 1.3** (Model API) | Cloud: words, and screenshots of web pages you ask to see | Plans searches and multi-part requests; web answers with sources; computer use |
| **Muse Image 1.0** (Model API) | Cloud: words only | Pictures and the map of your things |

**Pictures and voice from a home never leave it.** The camera and microphone reach only models on the computer beside
the robot. Every turn, the TV shows a privacy receipt: exactly which words went to which cloud model, or "Nothing left
this house"; "Andy, what did you send to the cloud today?" adds up the day's. Unplug the network and Andy carries on.
(The one exception is a switch for filming in a staged room: SAM 3.1 through the API, and the TV says so.)

## Technical depth (what was hard)

- **A point checked by its own camera.** The motors said Andy pointed within 3 degrees; its own camera showed
  the head sagging a few degrees after its pointing nod, so sending the same angles again landed the same way: Andy now
  corrects the command by what the frame shows (at most twice). Over 34 unattended searches on the robot: 34 pointed, none failed, a median 5.2
  degrees from the middle of the view (the chair in front, where the head turns alone: 2.1 to 3.4; worst where the base
  turns too).
- **How far, from one frame.** MapAnything gives metric depth for the frame a thing was confirmed in, in 0.2 s beside
  SAM 3.1 on one GPU: the same keyboard read 0.92 to 1.00 m from five starting poses.
- **Every model Meta's, the voice too.** Meta's API has no voice, so Andy speaks with SeamlessM4T v2 (9% of words
  misheard by a speech recogniser, against 23 to 28% for MMS-TTS). On the robot's small speaker the founder picked,
  by ear, a version slowed 8%, cleared of rumble and lifted around 3 kHz; to fit it, Glimmer runs without its drafter.
- **Agents that can't move the robot by themselves:** named views and numbered places, never motor values; every
  argument checked in code; Andy's words built from what the tools did.
- **Telling my mug from yours.** DINOv2 ignores colour (a blue and a red mug of one shape: 0.94 alike), so half the
  likeness is a colour fingerprint of the mug's own pixels: red 0.55, the same thing from other angles 0.79 to 0.98.
- **Identical cups, crossing.** Object Multiplex tracks about 4 frames a second on a 3090; at 5 frames a second of
  video the cups were lost every time, so Andy records at 10 and replays.
- **Computer use with a reviewer.** Every action is reviewed in code: nothing personal is typed, sign-in and payment
  pages end the run, the browser can't reach the home network, and Prompt Guard 2 stops a page that tries to instruct
  Andy (0.06 s).

## Measured

*Search, simulated* (the robot's camera model, seeded rooms; rerun Oct 30 on the final code): with look-alikes
described, the fixed sweep pointed at the wrong one 20 times in 100; **Glimmer's plan 18 of 20, 2 wrong** (Muse Spark
18 of 20, 1 wrong). Things behind the robot: **Glimmer 20 of 20 in 4.5 looks** (Spark 18 in 4.2; fixed sweep 92 of 100
in 7.1). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12** (6 of 12 before the
fixes this scorecard showed were needed), **Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every request the program made recorded on its way
out): **no camera picture reached the cloud** (24 taken); **every word from the home that was sent was on its turn's
receipt**; crisis words reached no model; offline, nothing at all went.
*Spanish:* **41 of 41** written requests reach the right ability; **34 of 41** said by Andy's own voice and heard
back (slips on the synthetic voice).
*On the robot, alone in the room:* **34 of 34** unattended searches ended in a point with no errors, a median 10.8 s
with the camera check; [the physical scorecard, judged by a person: N of M].
*Not yet tried on the robot with real things or a person:* the cup game (synthetic shuffles: 3 of 5), my mug, "what's
that?" (public photos: 4 of 6), going out (robot simulated). Every result, failures included: `evals/results/` and
`docs/research.md`.

## Safety and honesty

**Andy gives no health advice:** no medical, medication or mental-health advice, interpretations or recommendations.
It says it's an AI at the start of a conversation and every three hours. Crisis words, in English or Spanish, get the
988 line from code and reach no other model, checked twice on this computer: a word list, then Llama Guard 3 (it caught
3 of 8 phrasings the list missed, no false alarms on 12 ordinary ones, 0.04 s). It never asks for money or passwords.
Speech that isn't for Andy is dropped, never shown or kept. Model API spend is capped.

## What's next

Our own robot body (in design), the same software behind the same body interface; more languages; and the physical
scorecard in more homes.
