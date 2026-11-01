# Submission text (for the form on November 4)

*About 1,400 words, and 200 more in the table (trimmed on November 1; the longer version is in this file's history). Fill in the
[brackets] on the day; check every number against `evals/results/` first.*

---

**Andy: a tabletop robot that finds what you've lost, points at it, and keeps your private life private.**

HeyAndy, Inc. · Startup track · *Push the Frontier* (robotics) · Video: [link] · Live screen: huggingface.co/spaces/heyandy-ai/andy (and Andy's eyes, live in your browser: …/eyes.html) · Code: github.com/AndyDM9/heyandy-meta

**Before this week:** a Reachy Mini Lite robot, and our own earlier object-finding prototype (none of its code is in
this repository). **Everything below was built this week, on Meta's models. Every model Andy runs is Meta's.**

## The problem

Three in four adults 50 and older want to stay in their own homes as they age (AARP, 2024), and a quarter of Americans
65 and older live alone (Pew Research, 2025): when the glasses go missing, there's no one to ask "have you seen my
glasses?". People who live at home lose the same few things every day: glasses, keys, the phone, the remote, and many
of them speak another language first. A phone app can't look for them, and a camera that streams the living room to the cloud
is a camera most people won't have. Andy sits on the table, looks around the room for you, points at the thing, and
keeps what it sees and hears in the house.

## What it does

- **"Hey Andy, where are my glasses?"** Andy turns to your voice and looks around, the TV showing each view with SAM
  3.1's outlines. It points, checks with its own camera that the point landed, and says "There they are! To my left,
  about 5 feet away" (MapAnything measures how far). It skips a picture of glasses on the TV, and picks "the blue cup"
  from look-alikes.
- **"Hey Andy, I fell and I can't get up."** "If you need help, please call 911 right away. I'll find your phone."
  Andy searches for the phone and points at it (16.5 s on the robot): it can't call anyone, but it can find the phone.
- **In fifteen languages, and it notices which.** Say "安迪，我的眼镜在哪里？" and Andy switches and answers in Mandarin:
  Omnilingual ASR hears, Muse Glimmer translates on the computer beside the robot, SeamlessM4T v2 speaks. Saying it's an
  AI and the crisis reply are written by hand in each language.
- **The public demo, in your browser, on Meta's models.** Tap 🎙 and wav2vec 2.0 hears you (the demo's phrases scored
  against the sound, CTC: "whirl my keith" still finds your keys; 7 of 7 fresh clips); or show Andy's eyes (DINOv2) your
  mug and sweep your phone round the room: warmer, colder, a closer look, the spotlight. Nothing leaves the browser.
- **Meta's models, live, and under the hood.** The TV shows each model call as it happens and lays out each turn stage
  by stage; that showed the answer waiting for the point, so Andy now answers while pointing, 9.6 s sooner.
- **It remembers, and doesn't give up.** What you tell it ("my passport is in the top drawer"), where things live ("is
  everything home?"), and a missed search becomes a promise: when the thing turns up, Andy points and says so,
  unprompted. **V-JEPA 2** notices a watched thing put down.
- **"I'm ringing my phone"** turns Andy to the ringing; **"help me reach it"** talks a hand onto the thing ("toward
  you, and right") for someone who can't see well; **"show me the room"** makes its shape in 3D from five looks.
- **And:** reminders delivered in person; "I'm going out" (it points at what's still here); "this is my mug", "what's
  that?" and the cup game (SAM 3.1 Object Multiplex; not yet tried with a person); the weather radar on the TV (Muse
  Spark's computer use); a map of my things (Muse Image); several requests at once through an agent.

## Meta's models, and where each one runs

| Model | Where | What it does |
|---|---|---|
| **SAM 3.1** (open weights) | GPU 1, beside the robot | Finds things and the person; **Object Multiplex** tracks every cup at once |
| **Muse Glimmer 30B** (open weights, llama.cpp) | GPU 0 | Conversation; plans searches offline; checks pictures; translates Andy's fourteen other languages |
| **MapAnything** (open weights) | GPU 1 | How far a found thing is; the room in 3D from five looks |
| **V-JEPA 2** (open weights) | GPU 1 | Notices a watched thing put down or picked up (not yet tried with a person) |
| **Omnilingual ASR**, **SeamlessM4T v2** (open weights) | GPU 1, GPU 0 | Hears the person; Andy's voice; fifteen languages |
| **DINOv2** (open weights) | GPU 1; and in the visitor's browser on the public demo | Knows the person's own things by sight |
| **Llama Guard 3 8B**, **Llama Prompt Guard 2** (open weights) | GPU 1 | A second crisis check, and reads each sentence of a model's answer for health advice; reads each web page before Muse Spark does |
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
100; **Glimmer's plan 18 of 20, 2 wrong** (Muse Spark 18 of 20, 2 wrong). Things behind the robot: **Glimmer 20 of 20
in 4.6 looks** (fixed sweep 92 of 100 in 7.1). Nothing there: no false finds.
*The agent* (12 multi-part requests, scored on what the robot did): **Muse Spark 12 of 12, Glimmer offline 12 of 12**.
*The privacy audit* (a day of 21 requests with the real models, every outgoing request recorded): **no camera picture
reached the cloud** (24 taken); **every word sent was on its turn's receipt**; crisis words reached no model.
*Languages:* written requests reach the right ability, Spanish **41 of 41**, thirteen more **104 of 104** (the first
run, 100, showed rules missing); said aloud by Andy's voice and heard back, 36 of 41 and 89 of 104; called in one of
the fourteen, Andy switched to it 31 times in 42, never to a wrong one.
*Andy's eyes in the browser* (museum photos): found 20 of 24, never a wrong one; never "found" without it (24 tables);
sweeping live (a video as the camera, on a CPU): found in both sweeps, at 15 and 34 s; never in 90 frames without it.
*On the robot, alone in the room:* **112 of 112** unattended searches since the aim fix ended in a point; on the final
code, a median 5.2 degrees off the middle of the view, 8.3 at worst, 11.7 s. A find from request to spoken answer, 13
to 19 s. [The physical scorecard, judged by a person: N of M.]
Every result, failures included: `evals/results/` and `docs/research.md`.

## Safety and honesty

**Andy gives no health advice:** no medical, medication or mental-health advice, interpretations or recommendations,
kept in code: a health question gets Andy's own words, by hand in each language, and no model answers it (held out,
25 of 34 caught by the rule, none of the rest judged advice; 0 of 116 everyday requests caught), and Llama Guard 3
reads each sentence a model writes before Andy says it. It says it's an AI at the start of a conversation and every
three hours. Crisis words, in any of its fifteen languages, get the 988 line from code and reach no other model, checked
on this computer (a word list, then Llama Guard 3); the reply is written by hand in each language. Measured: 60 of 60
indirect phrasings, none of 144 everyday requests and trick remarks taken for one; and we publish the limit: warning
signs said in ways no list has, 16 of 45, all by Muse Glimmer's narrow third look. Ask **"Hey Andy, what won't you
do?"** and it says so, with today's receipts on the TV. Speech that isn't for Andy is dropped, never kept.

## What's next

Our own robot body (in design), the same software behind the same body interface; each language tried with people who
speak it; and the physical scorecard in more homes.
