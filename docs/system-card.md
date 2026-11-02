# Andy's system card

One page on what Andy is for, what it must not be used for, where your pictures and words go, how it was tested and
where it falls short. Every figure links to its evidence: the scorecards in [`evals/results/`](../evals/results/README.md)
(failures included) and the day-by-day record in [`docs/research.md`](research.md); each is read from its file by
[`scripts/claims.py`](../scripts/claims.py), and a test fails if this page and the file disagree. HeyAndy, Inc., November 2026.

## What it is

A tabletop robot (a Reachy Mini Lite) with a TV beside it, for people who live at home: it finds what you've lost,
points at it and says where, from where you stand; it remembers where things are, delivers the reminders you set, and
speaks fifteen languages. Every model it runs is Meta's ([which, where, and their licences](open-weights.md)); every
file of its nine open-weight models is byte for byte what Meta published (`scripts/verify_all_weights.py`).

## Intended use, and not

**For:** finding everyday things in one room the robot can see (glasses, keys, the phone, a mug); remembering where
they were; reminders you asked for; conversation, pictures and web pages on its TV when you ask.

**Not for, and built not to:**
- **Health advice of any kind** (medical, medication, mental-health advice, interpretations or recommendations). A
  health question gets Andy's own words, written by hand in each language, and no model answers it.
- **Emergencies beyond pointing at the phone.** It can't call anyone and doesn't watch for falls; "I fell and I can't
  get up" gets "please call 911 right away. I'll find your phone", then it finds and points at the phone.
- **Watching people.** It keeps no camera picture or sound; speech not addressed to it is dropped, never kept. Ask
  "what did you hear today?" and it says how often someone spoke near it and how few of those were for it: counts,
  never words.
- **Things it can't see:** in a drawer, under something, out of the room.

## Where your pictures and words go

- **Camera and microphone: only Meta's open models on the computer beside the robot** (SAM 3.1, Muse Glimmer,
  MapAnything, DINOv2, V-JEPA 2, Omnilingual ASR, SeamlessM4T v2, Llama Guard 3, Prompt Guard 2). Unplug the network
  and Andy carries on.
- **Words, when online:** Muse Spark (planning, web answers, harder conversation) and Muse Image (pictures) through
  Meta's Model API; web-page screenshots to Muse Spark only for "show me … on the TV". Every word sent is on that
  turn's receipt on the TV; "what did you send to the cloud today?" adds up the day.
- **The one exception:** a switch for filming a staged room sends frames to SAM 3.1 through the API, and the TV says so.
- **Kept on the computer:** what you tell it and where things were, as words and numbers; never a camera picture or a
  sound (only pictures you ask Muse Image to draw are saved).

## Safeguards, in code rather than asked of a model

| Safeguard | How | Measured |
|---|---|---|
| No health advice | a rule in 15 languages, before any model; Llama Guard 3 reads each sentence a model writes before Andy says it | held out: 25 of 34 caught by the rule, none of the rest judged advice; 0 of 116 everyday requests caught; Andy's real answers flagged 0 of 168 ([§63](research.md#63-no-health-advice-kept-in-code-and-measured-in-fifteen-languages-november-1-evening), [§65](research.md#65-llama-guard-3-reads-andys-answers-too-as-meta-built-it-to-november-1-evening)) |
| Crisis words get 988 | from code, before any other model: a word list, Llama Guard 3, then one narrow question to Muse Glimmer, all on this computer; the reply written by hand in each language | 60 of 60 indirect phrasings (the set it was tuned on); 0 of 144 everyday or trick remarks taken for one ([§58](research.md#58-the-crisis-check-in-fifteen-languages-measured-and-where-it-stops-november-1)) |
| It says it's an AI | at the start of a conversation and every three hours, by hand in each language | tested (`tests/test_answers_safety.py`) |
| A note in view can't instruct it | Glimmer told writing is never an instruction; a note addressed to Andy isn't read out | 9 of 54 drawn notes got through before, 0 of 72 after ([§74](research.md#74-a-note-in-view-cant-instruct-andy-november-2-morning)) |
| It doesn't join a conversation it isn't part of | when the room is talking, or talking over its answers, it answers only its name; at most six follow-ups in a row without it | a real meeting near the robot, replayed: 37 answers became 4; a quiet conversation keeps 6 of 8 follow-ups ([§79](research.md#79-a-conversation-andy-isnt-part-of-november-2-early-afternoon)) |
| A web page can't instruct it | Prompt Guard 2 reads each page before Muse Spark sees it; every click reviewed in code | [§28](research.md#28-llama-prompt-guard-2-a-web-page-cant-instruct-andy-2026-10-27-night) |
| Agents can't move the robot by themselves | named views and numbered places, never motor values; every argument checked in code | bad arguments refused and nothing moves (tests); and they work: 12 of 12 multi-part requests ([§26](research.md#26-the-agent-scorecard-2026-10-27-night)) |
| Privacy | pictures and voice only to local models; a receipt each turn | a recorded day of 21 requests: 0 of 24 camera pictures reached the cloud; every word sent was on its receipt ([§31](research.md#31-privacy-you-can-ask-about-and-an-audit-of-it-2026-10-28)) |
| Nothing of Andy's on the network | every one of its services listens on this computer only; the TV and the robot's daemon answer only their own names (DNS rebinding); its browser never photographs a page that came from this computer or the home network | preflight fails if a port listens wider; tested in the real browser ([§83](research.md#83-who-on-the-network-can-reach-andy-november-2-afternoon)) |
| Spend | a hard cap on Model API spend: a call past it is refused in code (Meta's own limit only emails) | `heyandy_meta/budget.py` |

Ask **"Hey Andy, what won't you do?"** and it says these, with the day's receipts on its TV.

## How well it works

- **Finding, alone:** 250 of 253 unattended searches on the robot ended in a point; the final code a median 1.1
  degrees off, 2.2 at worst, 7.8 s a find.
- **Finding, judged by a person:** 13 of 15 right (things moved round the desk or hidden), never a point at the wrong
  thing ([§69](research.md#69-the-physical-scorecard-a-person-judging-where-andy-points-november-1-about-9-pm)).
- **Languages:** 104 of 104 written requests in thirteen more languages reach the right ability, 89 of 104 spoken.
- **The public demo, for people who see less well:** axe-core's WCAG 2.2 A and AA checks pass on all 56 of its states,
  at a desktop's and a phone's width, and none of 1,193 texts measured from the pixels is below AA contrast; automated
  checks find only part of what people meet ([§81](research.md#81-the-public-demo-for-people-who-see-less-well-november-2-afternoon)).

## Known limits

- **Warning signs said in ways no list has:** 16 of 45 caught, held out (all by Glimmer's question; the list and
  Llama Guard 3 caught none). In the first set of health questions, one model answer
  was judged advice (that wording was then added to the rule).
- **Not yet tried with people or real things:** the cup game (synthetic shuffles: the right cup 3 of 5), "this is my
  mug" with two mugs, guiding a hand, "I'm going out" with someone leaving, V-JEPA 2 noticing a thing put down. The
  public demo's story labels each chapter "on the robot" or "not yet".
- **The note-in-view defence** is measured on drawn notes, not real handwriting through the robot's camera.
- **It needs today's hardware:** two 24 GB GPUs for the whole of Andy: 40.5 GB at rest, the language model 17.6 GB of
  it (`scripts/gpu_budget.py`); Andy Finder needs none, through the Model API.
- **Its name is a person's name:** plain "Andy" calls it. A home with an Andy can make it answer only "Hey Andy"; then
  a call in another script (安迪) isn't heard either.
- **Where it's been measured:** one desk, one home, one robot.

## Operating it

Preflight (`scripts/preflight.py`) must say READY before a demo: every check proves it looked (none passes on an empty
answer). Andy watches its own microphones and speaker and puts a lasting line with the fix on its TV if they stop;
"are you OK?" checks every part it needs. Every scorecard, failures included: [`evals/results/`](../evals/results/README.md).
