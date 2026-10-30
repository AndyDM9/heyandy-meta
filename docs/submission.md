# Submission text (draft, for the form on November 4)

*About 1,350 words with the table. Fill in the [brackets] on the day; check every number against `evals/results/` first.*

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

- **"Andy, where are my glasses?"** Andy turns to your voice, looks around the room (the TV shows each view live,
  every candidate outlined by SAM 3.1), points, then checks with its own camera that the point landed: "There they
  are! On the armchair, to my left, about 5 feet away" (MapAnything, Meta's 3D model, measures how far). It skips a
  picture of glasses on the TV, picks "the blue mug, next to the laptop" from look-alikes, and goes straight "behind
  you, on the left".
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
- **"Show me the weather radar on the TV."** Muse Spark picks the page and its computer use brings the radar into view,
  each step on the TV.
- **"Draw me a lighthouse at dawn"**, **"draw me a map of my things"** (Muse Image, from words only), questions about
  the world with their sources, conversation, and **"habla español"**: Andy hears, speaks and shows the TV in Spanish.
- **Several things at once:** "find my glasses, then my keys, then remind me in an hour to leave" goes to an agent with
  Andy's everyday abilities as tools (Muse Spark, or Glimmer offline).

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; says what it sees; translates Spanish |
| **Omnilingual ASR** (open weights) | GPU 1 | Hears the person, in English or Spanish |
| **DINOv2** (open weights) | GPU 1 | Knows the person's own things by sight |
| **MapAnything** (open weights, Apache-2.0) | GPU 1 | How far away a found thing is, from one frame; the TV's floor plan of your things |
| **Llama Prompt Guard 2** (open weights) | GPU 1 | Reads each web page first: one that tries to instruct Andy ends the run |
| **Llama Guard 3 8B** (open weights, 4-bit, converted here) | GPU 1 | A second crisis check on what the person says, before any other model |
| **Muse Spark 1.3** (Model API) | Cloud: words, and screenshots of web pages you ask to see | Plans searches and multi-part requests; web answers with sources; computer use |
| **Muse Image 1.0** (Model API) | Cloud: words only | Pictures and the map of your things |
| **SeamlessM4T v2** (open weights, its speech half) | GPU 0 | Andy's voice, English and Spanish (0.3 s a sentence); **every model Andy runs is Meta's** |

**Pictures and voice from a home never leave it.** The camera and microphone reach only models on the computer beside
the robot. Every turn, the TV shows a privacy receipt: exactly which words went to which cloud model, or "Nothing left
this house"; "Andy, what did you send to the cloud today?" adds up the day's. Unplug the network and Andy carries on.
(The one exception is a switch for filming in a staged room: SAM 3.1 through the API, and the TV says so.)

## Technical depth (what was hard)

- **A point checked by its own camera.** The motors said Andy pointed within 3 degrees; its camera said 7. The head
  sags about 4 degrees after its pointing nod, so sending the same angles again lands the same way. Andy now corrects
  the command by what the frame shows: things in front end within 2 degrees of the middle of its view (0.5, 1.6, 1.8);
  past the head's reach, where the base turns too, still 5 to 9, and we say so.
- **How far, from one frame.** MapAnything (Meta's open 3D model) gives metric depth for the frame a thing was
  confirmed in, in 0.2 s on the GPU beside SAM 3.1: the same keyboard read 0.59 to 0.67 m from four starting poses.
  Memory keeps each place's distance, and the TV draws a floor plan in feet.
- **Every model Meta's, the voice too.** Meta's API has no voice, so Andy speaks with Meta's open SeamlessM4T v2
  (9% of words misheard by a speech recogniser, against 23 to 28% for MMS-TTS). On the robot's small speaker it was
  still hard to follow, so five versions were played there and the founder picked one: slowed 8%, cleared of rumble,
  6 dB around 3 kHz, never clipped (a soft clipper had blurred the consonants). To fit it, Glimmer runs without its
  drafter (39 tokens a second instead of 53; what it says is unchanged).
- **Agents that can't move the robot by themselves:** named views and numbered places, never motor values; every
  argument checked in code; Andy's words built from what the tools did.
- **Identical cups, crossing.** Object Multiplex tracks about 4 frames a second on a 3090; at 5 frames a second of
  video the cups were lost every time, so Andy records at 10 and replays.
- **Telling my mug from yours.** DINOv2 ignores colour (a blue and a red mug of one shape: 0.94 alike), so half the
  likeness is a colour fingerprint of the mug's own pixels: red 0.55, the same thing from other angles 0.79 to 0.98.
- **Straight to the answer.** Glimmer reasons before every answer, whatever its setting. Starting its reply past the
  reasoning cut its picture checks from 1.9 s to 1.1 s (same accuracy) and a find on the robot from 8.5 s to 7.1 s.
- **Computer use with a reviewer.** Every batch of actions is reviewed in code before Meta's safety check is
  acknowledged: nothing personal is typed, sign-in and payment pages end the run, the browser can't reach the home
  network, and Llama Prompt Guard 2 reads each page first (hidden "ignore your instructions" text: stopped in 0.06 s).

## Measured

*Search, simulated* (the robot's camera model, seeded rooms): with look-alikes described, the fixed sweep pointed at the
wrong one 20 times in 100; **Glimmer's plan 19 of 20, 1 wrong** (Muse Spark 18 of 20, 1 wrong). Things behind the robot:
**19 of 20 in 3.8 looks** (Spark 18 in 3.3; fixed sweep 92 of 100 in 6.2). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12** (6 of 12 before the fixes
this scorecard showed were needed), **Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every request the program made recorded on its way
out): **no camera picture reached the cloud** (18 taken); **every word from the home that was sent was on its turn's
receipt** (the rest were Andy's own instructions); crisis words reached no model; offline, nothing at all went.
*Spanish:* **41 of 41** written requests and **40 of 41** spoken ones reach the right ability (after two translation
rules this scorecard showed were needed).
*On the robot:* a cup found in 7.5 s and a keyboard in 7.1 s; first word 0.7 to 1 s after Andy understands you;
alone in the room, 12 of 12 unattended searches ended in a point with no errors (8.7 to 11.8 s, the camera check
included); [the physical scorecard: N of M].
*Not yet tried on the robot with real things or a person:* the cup game (synthetic shuffles: 3 of 5), my mug, "what's
that?" (public photos: 4 of 6), going out (robot simulated). Every result, failures included: `evals/results/` and `docs/research.md`.

## Safety and honesty

Andy says it's an AI at the start of a conversation and every three hours. Crisis words, in English or Spanish, get
the 988 line from code and reach no other model, checked twice on this computer: a word list, then Llama Guard 3 (it
caught 3 of 8 phrasings the list missed, no false alarms on 12 ordinary ones, 0.04 s). No medical advice; it never
asks for money or passwords. Speech that isn't for Andy is dropped, never shown or kept. Model API spend is capped.

## What's next

Our own robot body (in design), the same software behind the same body interface; more languages; and the physical
scorecard in more homes.
