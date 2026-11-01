# Submission text (for the form on November 4)

*About 1,270 words, and 200 more in the table (trimmed on November 1; the longer version is in this file's history). Fill in the
[brackets] on the day; check every number against `evals/results/` first.*

---

**Andy: a tabletop robot that finds what you've lost, points at it, and keeps your private life private.**

HeyAndy, Inc. · Startup track · *Push the Frontier* (robotics) · Video: [link] · Live screen: huggingface.co/spaces/heyandy-ai/andy (and Andy's eyes, live in your browser: …/eyes.html) · Code: github.com/AndyDM9/heyandy-meta

**Before this week:** a Reachy Mini Lite robot, and our own earlier object-finding prototype (none of its code is in
this repository). **Everything below was built this week, on Meta's models. Every model Andy runs is Meta's.**

## The problem

People who live at home lose the same few things every day: glasses, keys, the phone, the remote, and many of them
speak another language first. A phone app can't look for them, and a camera that streams the living room to the cloud
is a camera most people won't have. Andy sits on the table, looks around the room for you, points at the thing, and
keeps what it sees and hears in the house.

## What it does

- **"Hey Andy, where are my glasses?"** Andy turns to your voice and looks around; the TV shows each view live, every
  candidate outlined by SAM 3.1. It points, checks with its own camera that the point landed, and says "There they
  are! On the armchair, to my left, about 5 feet away" (MapAnything measures how far). It skips a picture of glasses
  on the TV, picks "the blue cup" from look-alikes, and says so when the red one you asked for isn't there.
- **In fifteen languages.** "Andy, speak Mandarin": Omnilingual ASR hears it, Muse Glimmer translates on the computer
  beside the robot, SeamlessM4T v2 speaks it, and every ability works. Saying it's an AI, the crisis reply and Andy's
  short lines are written by hand in each, never machine-translated.
- **Andy's eyes, live, in your browser.** The public demo runs one of Meta's models for the visitor: show it your mug
  once, then sweep your phone's camera round the room. DINOv2 looks at every moment of it in the browser (nothing goes
  anywhere), a tone gets warmer as you near it, and a confident sighting gets a closer look, as on the robot, before
  the spotlight: *yours*, alike and the same colour, or it asks.
- **Meta's models, live, and under the hood.** The TV shows each Meta model call as it happens, timed, and where it
  runs, and lays out each turn stage by stage; that showed the answer waiting for the point, so now Andy answers while
  pointing, 9.6 s sooner.
- **It remembers, and doesn't give up.** "I'm putting my passport in the top drawer" is kept in your words; "is
  everything home?" points at what's away, then where it lives; a missed search becomes a promise, and when the thing
  turns up Andy points and says so, unprompted. **V-JEPA 2** notices a watched thing put down.
- **"I'm ringing my phone"** turns Andy until its microphones hear the ringing straight ahead; it looks there and
  points. **"Help me reach it"**, for someone who can't see well: Andy watches their hand and talks it onto the thing
  ("Toward you, and right"), SAM 3.1 finding the hand and the thing in each frame.
- **"Show me the room."** Five looks, joined by MapAnything into the room's shape in 3D on the TV: dots, never a
  picture, your things pinned with their distances.
- **And:** reminders delivered in person; "I'm going out" (it points at what's still here; Muse Spark checks for
  rain); "this is my mug", "what's that?" and the cup game (SAM 3.1 Object Multiplex; not yet tried with a person); the
  weather radar on the TV (Muse Spark's computer use); a map of my things (Muse Image); several requests at once
  through an agent with Andy's abilities as tools.

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; translates Andy's fourteen other languages |
| **MapAnything** (open weights) | GPU 1 | How far a found thing is; the room in 3D from five looks |
| **V-JEPA 2** (open weights) | GPU 1 | Notices a watched thing put down or picked up (not yet tried with a person) |
| **Omnilingual ASR**, **SeamlessM4T v2** (open weights) | GPU 1, GPU 0 | Hears the person; Andy's voice; fifteen languages |
| **DINOv2** (open weights) | GPU 1; and in the visitor's browser on the public demo | Knows the person's own things by sight |
| **Llama Guard 3 8B**, **Llama Prompt Guard 2** (open weights) | GPU 1 | A second crisis check; reads each web page before Muse Spark does |
| **Muse Spark 1.3** (Model API) | Cloud: words, and screenshots of web pages you ask to see | Plans searches and multi-part requests; web answers; computer use |
| **Muse Image 1.0** (Model API) | Cloud: words only | Pictures and the map of your things |

**Pictures and voice from a home never leave it.** The camera and microphone reach only models on the computer beside
the robot. Every turn, the TV shows a privacy receipt: exactly which words went to which cloud model, or "Nothing left
this house"; "Hey Andy, what did you send to the cloud today?" adds up the day's. Unplug the network and Andy carries on.
(The one exception is a switch for filming in a staged room: SAM 3.1 through the API, and the TV says so.)

## Technical depth (what was hard)

- **A point checked by its own camera.** The camera showed the head sagging after its pointing nod, and that the base's
  turn was being added twice; the command is now corrected by what the frame shows (worst point 13.7 degrees off the
  middle of the view before, under 9 after).
- **The room in 3D.** MapAnything alone made five looks 1.3 times too wide; with its depth, Andy's own rays and the
  head's measured angles, looks agree to a median 0.9 degrees, and scan to scan within 1.
- **Every model Meta's, the voice too.** Meta's API has no voice, so Andy speaks with SeamlessM4T v2 (9% of words
  misheard by a speech recogniser, against 23 to 28% for MMS-TTS), tuned by ear on the robot's small speaker.
- **Agents that can't move the robot by themselves:** named views and numbered places, never motor values, every
  argument checked in code, and Andy's words built from what the tools did. Web pages: Prompt Guard 2 reads each first.
- **Telling my mug from yours.** DINOv2 ignores colour (a blue and a red mug of one shape: 0.94 alike), so half the
  likeness is a colour fingerprint of the mug's own pixels, on the robot and in the browser.

## Measured

*Search, simulated* (seeded rooms): with look-alikes described, the fixed sweep pointed at the wrong one 20 times in
100; **Glimmer's plan 18 of 20, 2 wrong** (Muse Spark 18 of 20, 1 wrong). Things behind the robot: **Glimmer 20 of 20
in 4.6 looks** (fixed sweep 92 of 100 in 7.1). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12, Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every outgoing request recorded): **no camera picture
reached the cloud** (24 taken); **every word sent was on its turn's receipt**; crisis words reached no model.
*Languages:* Spanish **41 of 41** written requests reach the right ability, **36 of 41** said aloud and heard back;
thirteen more (Mandarin to Ukrainian, 104 requests) **100 and 85** on the first run, 104 and 89 with the rules it showed
were missing.
*Andy's eyes in the browser* (museum photos): found 20 of 24, never a wrong one; never "found" without it (24 tables);
sweeping live (a video as the camera, on a CPU): found in both sweeps, at 15 and 34 s; never in 90 frames without it.
*On the robot, alone in the room:* **112 of 112** unattended searches over two days ended in a point; on the final
code, a median 5.2 degrees off the middle of the view, 8.3 at worst, 11.7 s. A find from request to spoken answer, 13
to 19 s. [The physical scorecard, judged by a person: N of M.]
Every result, failures included: `evals/results/` and `docs/research.md`.

## Safety and honesty

**Andy gives no health advice:** no medical, medication or mental-health advice, interpretations or recommendations.
It says it's an AI at the start of a conversation and every three hours. Crisis words, in any of its fifteen languages,
get the 988 line from code and reach no other model, checked twice on this computer (a word list, then Llama Guard 3);
the reply is written by hand in each language (in thirteen: call and ask for an interpreter). It never asks for money
or passwords. Speech that isn't for Andy is dropped, never shown or kept. Model API spend is capped.

## What's next

Our own robot body (in design), the same software behind the same body interface; each language tried with people who
speak it; and the physical scorecard in more homes.
