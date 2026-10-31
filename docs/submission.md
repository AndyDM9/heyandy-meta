# Submission text (for the form on November 4)

*About 1,450 words with the table. Fill in the [brackets] on the day; check every number against `evals/results/` first
(the scorecards were rerun on October 30 and 31 on the final code).*

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

- **"Hey Andy, where are my glasses?"** Andy turns to your voice and looks around; the TV shows each view live, every
  candidate outlined by SAM 3.1. It points, checks with its own camera that the point landed, and says "There they
  are! On the armchair, to my left, about 5 feet away" (MapAnything measures how far). It skips a picture of glasses
  on the TV, picks "the blue cup" from look-alikes, and says so when the red one you asked for isn't there.
- **"Help me reach it."** For someone who can't see well, Andy then watches their hand and talks it onto the thing
  from their side ("Toward you, and right"), with notes that rise as the hand nears, like a parking sensor: SAM 3.1
  finds the hand and the thing in each frame, on the computer beside the robot.
- **"Hey Andy, show me the room."** Five looks, SAM 3.1 marking your things in each, joined by MapAnything into the room's
  shape in 3D on the TV: dots, never a picture, your things as pins with their distances. Gone in two minutes.
- **"Keep an eye on my keys."** Andy remembers where your chosen things were last seen, in words ("on the desk, behind
  the keyboard") and how far. While it watches and you're in view, **V-JEPA 2** notices a watched thing put down and
  updates its place.
- **"Remind me at 3 pm to call Sam."** At the time, Andy finds you with its camera, turns to you, and says it.
- **"Hey Andy, I'm going out."** Andy points at what's still here ("Don't forget your keys") while Muse Spark checks
  whether you'll need an umbrella.
- **"This is my mug"** (learned by sight, as numbers), **"what's that?"** (Andy looks where you point and points too),
  **the cup game** (SAM 3.1 Object Multiplex tracks every cup at once). Built and measured on photos and synthetic
  shuffles; not yet tried with a person in the room.
- **The weather radar on the TV** (Muse Spark's computer use), **a map of my things** (Muse Image, from words only),
  answers with sources, **Spanish**, the time and day from the clock, and several things at once through an agent with
  Andy's abilities as tools (Muse Spark, or Glimmer offline).

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; translates Spanish |
| **MapAnything** (open weights) | GPU 1 | How far a found thing is; the room in 3D from five looks |
| **V-JEPA 2** (open weights) | GPU 1 | Notices a watched thing put down or picked up (not yet tried with a person) |
| **Omnilingual ASR**, **SeamlessM4T v2** (open weights) | GPU 1, GPU 0 | Hears the person; Andy's voice; English and Spanish |
| **DINOv2** (open weights) | GPU 1 | Knows the person's own things by sight |
| **Llama Guard 3 8B**, **Llama Prompt Guard 2** (open weights) | GPU 1 | A second crisis check; reads each web page before Muse Spark does |
| **Muse Spark 1.3** (Model API) | Cloud: words, and screenshots of web pages you ask to see | Plans searches and multi-part requests; web answers; computer use |
| **Muse Image 1.0** (Model API) | Cloud: words only | Pictures and the map of your things |

**Pictures and voice from a home never leave it.** The camera and microphone reach only models on the computer beside
the robot. Every turn, the TV shows a privacy receipt: exactly which words went to which cloud model, or "Nothing left
this house"; "Hey Andy, what did you send to the cloud today?" adds up the day's. Unplug the network and Andy carries on.
(The one exception is a switch for filming in a staged room: SAM 3.1 through the API, and the TV says so.)

## Technical depth (what was hard)

- **A point checked by its own camera.** Andy's camera showed the head sagging after its pointing nod, so the command
  is corrected by what the frame shows. The same check found that the robot takes the head's direction in the room,
  the base's turn already in it: Andy had added the base again and, past 30 degrees, never faced as far round as it
  thought. Fixed: the worst point went from 13.7 degrees off the middle of the view to under 9.
- **A robot that measured its own lens.** Andy centred a watch, a cup and glasses, then saw each from 27 head angles:
  the published focal length put things up to 4.7 degrees out at the edges; two runs measured 1054 and 1049 px.
- **The room in 3D.** Joined by MapAnything alone, five looks came out 1.3 times too wide; with MapAnything's depth,
  Andy's own rays and the head's measured angles, looks agree to a median 0.9 degrees, and scan to scan within 1.
- **Noticing, built to fail safe.** V-JEPA 2 is asked only where something moved while the head held still, and a
  verdict costs one SAM 3.1 glance; on the empty table, 10 clips, nothing noticed.
- **Every model Meta's, the voice too.** Meta's API has no voice, so Andy speaks with SeamlessM4T v2 (9% of words
  misheard by a speech recogniser, against 23 to 28% for MMS-TTS), tuned by ear on the robot's small speaker.
- **Agents that can't move the robot by themselves:** named views and numbered places, never motor values; every
  argument checked in code; Andy's words built from what the tools did; the colour you asked for checked on the
  picture, alone, before any point.
- **Telling my mug from yours.** DINOv2 ignores colour (a blue and a red mug of one shape: 0.94 alike), so half the
  likeness is a colour fingerprint of the mug's own pixels.
- **Computer use with a reviewer.** Every action is reviewed in code: nothing personal is typed, sign-in and payment
  pages end the run, the browser can't reach the home network, and Prompt Guard 2 stops a page that tries to instruct
  Andy.

## Measured

*Search, simulated* (the robot's camera model, seeded rooms): with look-alikes described, the fixed sweep pointed at
the wrong one 20 times in 100; **Glimmer's plan 18 of 20, 2 wrong** (Muse Spark 18 of 20, 1 wrong). Things behind the
robot: **Glimmer 20 of 20 in 4.0 looks** (fixed sweep 92 of 100 in 7.1). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12** (6 of 12 before the
fixes this scorecard showed were needed), **Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every outgoing request recorded): **no camera picture
reached the cloud** (24 taken); **every word sent was on its turn's receipt**; crisis words reached no model.
*Spanish:* **41 of 41** written requests reach the right ability; **34 of 41** said by Andy's voice and heard back.
*On the robot, alone in the room:* **112 of 112** unattended searches over two days ended in a point; on the final
code, a median 5.2 degrees off the middle of the view, 8.3 at worst, 11.7 s. Typed to Andy on the robot: "the red
cup" with only a blue one there, no point 4 of 4; the blue one, 2 of 2; a find from request to spoken answer, 13 to
19 s. [The physical scorecard, judged by a person: N of M.]
Every result, failures included: `evals/results/` and `docs/research.md`.

## Safety and honesty

**Andy gives no health advice:** no medical, medication or mental-health advice, interpretations or recommendations.
It says it's an AI at the start of a conversation and every three hours. Crisis words, in English or Spanish, get the
988 line from code and reach no other model, checked twice on this computer: a word list, then Llama Guard 3. It never
asks for money or passwords. Speech that isn't for Andy is dropped, never shown or kept. Model API spend is capped.

## What's next

Our own robot body (in design), the same software behind the same body interface; more languages; and the physical
scorecard in more homes.
