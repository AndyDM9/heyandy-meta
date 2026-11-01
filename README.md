<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/heyandy-signature-reversed.svg">
    <img src="docs/images/heyandy-signature.svg" alt="HeyAndy" width="360">
  </picture>
</p>

# HeyAndy x Meta

**A tabletop robot that finds what you've lost, points at it, and keeps your home's pictures in your home.**
Built on Meta's models for people who live at home, starting with older adults, by **HeyAndy, Inc.**
([heyandy.ai](https://heyandy.ai)) for Meta's Global AI Developer Hackathon (startup track, *Push the Frontier*).

<p align="center">
  <img src="docs/images/reveal-loop.webp" width="860" alt="Andy's TV the moment it finds a mug: the room goes dark, a spotlight opens on SAM 3.1's outline of the mug, and the seconds to find it, the degrees off target its camera measured and the distance count up">
</p>

<p align="center">
  <a href="https://huggingface.co/spaces/heyandy-ai/andy"><img alt="Try the 1-minute story in your browser" src="https://img.shields.io/badge/%E2%96%B6%20Try%20it-the%201--minute%20story-ffcf5c?style=for-the-badge&labelColor=12241d"></a>
  <!-- On November 4, the video: <a href="VIDEO_URL"><img alt="Watch the 3-minute video" src="https://img.shields.io/badge/%E2%96%B6%20Watch-the%203--minute%20video-ffcf5c?style=for-the-badge&labelColor=12241d"></a> -->
  <a href="#why-its-different"><img alt="Every model Andy runs is Meta's" src="https://img.shields.io/badge/Every%20model-Meta's%20(11)-1e5f4a?style=for-the-badge&labelColor=12241d"></a>
  <a href="evals/results"><img alt="112 of 112 unattended searches on the robot ended in a point" src="https://img.shields.io/badge/On%20the%20robot-112%20of%20112%20pointed-1e5f4a?style=for-the-badge&labelColor=12241d"></a>
</p>

<sub>Above: the TV the moment Andy finds something (the demo scene's drawn picture, not a home).</sub>

**Ask Andy yourself, in the browser.** The demo opens as a one-minute story; type what you'd say to Andy at any point
("where are my keys?", "help me reach it", "I'm ringing my phone", "show me the room") and the scene recorded from its
TV for that plays, a search starting as the real one does. The words are matched in the page and sent nowhere; a link
can ask for you: add `?ask=I'm ringing my phone` to the demo's address.

**Andy gives no health advice:** no medical, medication or mental-health advice, interpretations or recommendations.
It finds things, remembers where they are, and delivers the reminders the person set. It says it's an AI, and anyone
who mentions a crisis gets the 988 line from code ([docs/crisis-protocol.md](docs/crisis-protocol.md)).

## What Andy does

| Finds it, and points | Guides your hand | Turns to a ringing |
|---|---|---|
| ![Found: the drawn mug outlined, "ahead of you, on your left, about 2 steps from you, at your 11 o'clock", a little map from where you stand](docs/images/tv-found.webp) | ![Guiding a hand: the mug and the hand outlined, a big arrow, "15 in from your hand"](docs/images/tv-guide.webp) | ![Listening for a phone: each turn of the head seen from above, and where it rings](docs/images/tv-sound.webp) |
| **"Hey Andy, where's my mug?"** SAM 3.1 finds it, Andy points and checks its own aim, and says it from where you stand: "ahead of you, on your left, about 2 steps, at your 11 o'clock". *112 of 112 searches on the robot ended in a point.* | **"Help me reach it."** For someone who can't see well: it watches your hand and the thing, and talks your hand in ("Toward you, and right") with notes that rise as you near it. *On the robot: no hand made up, in 34 frames of an empty table.* | **"I'm ringing my phone."** It turns until its microphones hear the ringing straight ahead, looks there, and points, even at a phone under a cushion. *6 of 6 ringings faced, within 20 degrees; a voice never.* |
| **It doesn't give up** | **Where things live** | **What you tell it** |
| ![It turned up: "Good news: your mug turned up!", and a wallet it's still looking for](docs/images/tv-turned.webp) | ![Is everything home? Two things home, the keys away, where they are and where they live](docs/images/tv-home.webp) | ![You told me: "I put my passport in the top drawer of the desk"](docs/images/tv-told.webp) |
| A miss becomes "I'll keep looking", and when the thing turns up, Andy points and says so, unprompted. *On the robot: a "lost" watch found later, 4.1 degrees off, said out loud.* | **"My keys live here." "Is everything home?"** It checks each home, points at what's away, then at where it lives; every evening at 9. *On the robot: the keys found away, pointed at, then their home.* | **"I'm putting my passport in the top drawer."** What no camera sees, it keeps in your words and answers at once: "You told me on Tuesday at 3:12". *On the robot: answered without a single look.* |
| **Your room in 3D** | **Ask Andy in your browser** | **Andy Finder, for every Reachy Mini** |
| ![The room in 3D: its shape from MapAnything, your things pinned with their distances](docs/images/tv-room.webp) | ![The public demo: "You asked: Where are my keys?", then the find](docs/images/demo-ask.webp) | ![Andy Finder: "Lost your phone? Ring it", and the turns to the ringing from above](docs/images/finder-ring.webp) |
| **"Show me the room."** Five looks become your room in 3D (MapAnything), your things pinned: its shape only, never a picture. *Scan to scan within 1 degree and 8 cm.* | Type what you'd say, and the scene recorded from Andy's TV for it plays, a search as the real one runs. [Try it](https://huggingface.co/spaces/heyandy-ai/andy); nothing typed is sent anywhere. | In the Reachy Mini app store: "Ring it" with nothing to set up (no key, no GPU, no internet), and anything else found with SAM 3.1 ([`apps/andy_finder`](apps/andy_finder)). |

<sub>Every picture above is the TV page itself, showing the demo's drawn scenes (`scripts/readme_shots.py` makes them
again); never a home. The numbers in italics are from the robot, with their files under Proof.</sub>

### Under the hood

![Under the hood: a search on the robot laid out stage by stage, to scale: hearing (Omnilingual ASR) 0.16 s, the safety check (Llama Guard 3), the head and base moving three times, the camera, SAM 3.1 seeing at each look, Muse Glimmer checking the picture, MapAnything measuring, SeamlessM4T v2 speaking; 15.4 s in all, the first sound at 0.16 s](docs/images/hood.webp)

The TV's gear (or "Hey Andy, how did you do that?") opens **Under the hood**: each turn timed live on the computer
beside Andy, stage by stage, with which of Meta's models did each and where it runs, every local service's health,
and recent turns in three lanes (the body, the models, the voice). It showed where a search's time went, and that
changed Andy: **it now answers the moment a find is confirmed, while its head turns to point and checks its aim**,
as a person points and speaks at once. Measured on the robot, the same search: the answer used to start 15.5 s after
the words and now starts at **5.8 to 6.0 s**; the whole turn went from 20.5 s to **10.7 to 11.0 s**. Only numbers and
names are kept, in memory: never a word said or a picture (`screen/hood.py`, `screen/hood.html`).

## Why it's different

- **It moves, and checks itself.** SAM 3.1's mask becomes the head's angle; after pointing, Andy's own camera measures
  where the point landed and corrects it. Andy even measured its own lens to do that well.
- **It knows where things are, not just what they are.** MapAnything gives every find a distance and the room a
  shape; V-JEPA 2, Meta's video world model, notices a watched thing being put down.
- **Private by design.** The camera and microphone reach only Meta's open models on the computer beside the robot;
  every word that goes to the cloud is shown on the TV's receipt. Unplug the network and Andy carries on.
- **Every model it runs is Meta's** (eleven): SAM 3.1, Muse Glimmer, MapAnything, V-JEPA 2, DINOv2, Omnilingual ASR,
  SeamlessM4T v2, Llama Guard 3 and Prompt Guard 2 on our hardware; Muse Spark and Muse Image through the Meta Model API.

## Proof

| | Measured | |
|---|---|---|
| On the robot, alone in the room | **112 of 112** unattended searches ended in a point; a median **5.2°** off the middle of the view on the final code | [`unattended-*`](evals/results) |
| Look-alikes, described ("the blue one") | Glimmer's plan **18 of 20**, the fixed sweep 80 of 100 (simulated); on the robot, "the red cup" with only a blue one there: **no point, 4 of 4** | [`sim-glimmer.json`](evals/results/sim-glimmer.json), [research §35](docs/research.md#35-typed-to-andy-on-the-robot-2026-10-31) |
| Several things at once | **12 of 12** with Muse Spark, **12 of 12** offline with Muse Glimmer | [`agent-spark.json`](evals/results/agent-spark.json) |
| Privacy, a day of 21 requests | **0** camera pictures reached the cloud; every word sent was on its turn's receipt | [`privacy-audit.json`](evals/results/privacy-audit.json) |
| The room in 3D | looks agree to a median **0.9°**; scan to scan within **1° and 8 cm** | [`room-20261031-1129.json`](evals/results/room-20261031-1129.json) |
| It doesn't give up | told a watch was lost, one look-again **found it, pointed 4.1° off and said so**, unprompted; nothing said of a wallet that wasn't there | [`lost-20261031-1653.json`](evals/results/lost-20261031-1653.json) |
| By its ring | **6 of 6** ringings turned to from three starts, within **20°**; a spoken sentence **never** taken for one; Andy Finder 4 of 4 | [`sound-20261031-1856.json`](evals/results/sound-20261031-1856.json), [`finder-ring-*`](evals/results) |
| Homes | the watch and the cup home, the keys **pointed at, then their home**, in 2 of 3 runs (the third: the search missed, and said so) | [`home-*`](evals/results) |
| How soon it answers | the same search, profiled: the answer started **15.5 s** after the words; now **5.8 to 6.0 s**, said while pointing; the turn **20.5 s → 10.7 to 11.0 s** | [research §50](docs/research.md#50-andy-answers-while-it-points-2026-10-31), [`hood-20261031-2036.json`](evals/results/hood-20261031-2036.json) |
| Are you OK? | everything: "I'm fine" in **2 s**; MapAnything stopped on purpose: **"Telling how far (MapAnything): I can still find things and point, but not say how far"** | [`selfcheck-20261031-1954.json`](evals/results/selfcheck-20261031-1954.json) |
| What it's told | asked where the passport is: **answered from the words, with no look and no frame** | [`told-20261031-1811.json`](evals/results/told-20261031-1811.json) |

Failures are kept too: every scorecard, and what changed because of it, is in `evals/results/` and `docs/research.md`.

## The details: what it does

**New here? "Hey Andy, let's get started."** Three steps, spoken, the TV showing each: Andy says what it does and that
what it sees and hears stays in the house, and measures the room in 3D; asks what you lose most ("my keys and my
glasses"), keeps an eye on them, looks for them all at once and points at each one it sees; then "Now try me: say,
'Hey Andy, where are my keys?'", and ends with the privacy promise. "Skip" ends it; crisis words still come first; when
nothing is set up, the TV suggests it. On the robot: the room, the keys and glasses watched and pointed at, the keys
found, "You're all set", in three sentences.

1. **Ask "where are my glasses?"** The robot looks around the room.
2. **SAM 3.1 finds them.** Its mask becomes the head's angle. The robot looks closer, checks, and points, then checks
   the point landed with its own camera. **MapAnything** (Meta's 3D model) says how far: "on the armchair, to my left,
   about 5 feet away", and the TV's map of your things becomes a floor plan, in feet.
   **Told from where you stand.** Andy's right is your left when you face it, so Andy doesn't say "to my right":
   as it turns to your voice it measures where you are (SAM 3.1 finds you, MapAnything says how far), and says where the
   thing is from your side, with a clock position as people with low vision are often given directions: "behind you,
   on your left, about 4 steps from you, at your 8 o'clock". The TV draws it as a little map from your point of view.
   If Andy can't see you, it says it from its own side, as before (`finder/perspective.py`).
   **"Hey Andy, help me reach it."** For someone who can't see well, the last half metre is where a hand sweeps the
   table and knocks the mug over. So Andy keeps its eyes on the thing and watches for your hand (SAM 3.1 finds both in
   each frame, about twice a second on the computer beside it) and talks your hand in, from your side: "Toward you, and
   right", "A little further", with a soft note between the words that rises as your hand gets nearer, like a parking
   sensor, then "That's it! Your mug is right at your fingertips." The TV shows the hand and the thing outlined, and a
   big arrow for the way to move (`companion/guide.py`).
   **It doesn't give up.** When a search misses ("I couldn't find your wallet from here"), Andy promises to keep
   looking ("I'll keep looking, and tell you when I see it") and does: every few minutes while the room is quiet, for
   up to two hours, one look around for everything still missing (SAM 3.1, all of them from one encoding of each
   view). A thing spotted gets the full search, which checks it and points; then, unprompted: "Good news: your watch
   turned up! It's a little to my right, about 3 feet away." The TV's side card and a paired phone show what Andy is
   still looking for; "I found it" or "stop looking" lets go (`memory/lost.py`). On the robot it found a watch it was
   told was lost, pointed 4.1 degrees off the middle and said so out loud, and kept quiet about a wallet that wasn't there.
   **Andy Finder, for every Reachy Mini owner** (`apps/andy_finder`, the Reachy Mini app store): the same "Ring it" with
   nothing to set up (no key, no GPU, no internet), and finding anything else with SAM 3.1.
   **"I'm ringing my phone."** A phone under a cushion is invisible to a camera, but it rings. Andy turns its head
   towards the ringing until its microphones hear it straight ahead, as a person turns to a sound, then looks only
   around that way with SAM 3.1, and points: "I followed the ringing. There it is!" Can't see it? It points where the
   sound is: "I can hear it, but I can't see it. It's ringing a little to my right: it may be under something." It waits
   up to 30 seconds for the ringing to start (dialling takes a while). A
   tracker on a key ring that beeps works the same way ("listen for my keys"); a voice is never taken for a ringing
   (most of a ringing is pure tone; a voice only now and then). Only each tenth of a second's loudness, tone and
   direction are kept, for 20 seconds; nothing is recorded (`companion/sound.py`). The TV draws each turn from above.
   **Homes: so things stop getting lost.** "Hey Andy, my keys live here" gives a thing a home where Andy sees it, in
   words ("on the desk, next to the lamp"). A search looks there first ("Right at home, where they live"). "Is
   everything home?" (and every evening at 9, by itself) looks at each home; a thing that isn't there is found,
   pointed at, and then its home is pointed at: "Your keys aren't home: they're a little to my right. They live there,
   in the bowl by the door." Not seen anywhere: Andy keeps looking. The TV lists each one, home or not
   (`memory/places.py`, `app.py home_check`).
   **"I'm putting my passport in the top drawer."** A camera sees one room; the things people dread losing are in
   drawers, bags and other rooms. Andy keeps what it's told, as your words with when you said them, and answers from
   them at once, without moving: "You told me on Tuesday at 3:12: your passport is in the top drawer of the desk."
   Asked again, it looks around the room; seen since by the camera, the camera wins; a search that misses says what
   you'd told it. "Forget my passport" removes it (`memory/told.py`).
   **"Hey Andy, are you OK?"** For someone who lives alone with a robot, the worst moment is Andy going quiet with no
   way to tell why. Andy checks each part it needs, as it uses them every turn (its camera; SAM 3.1, MapAnything,
   Muse Glimmer, the voice and Llama Guard 3 on the computer beside it; its microphones; its motors; its memory),
   times each, and says what works and what that means: "Mostly fine, but 1 thing isn't working. Telling how far
   (MapAnything): I can still find things and point, but not say how far." The TV lists every part; the cloud is
   never called for it (`companion/selfcheck.py`).
3. **The TV shows what Andy sees, live, as it searches** (each view, every candidate outlined by SAM 3.1), **then the
   picture it found them in,** with the mask drawn, the time, how far off target the point landed and how far away. The picture is kept in memory only, never saved.
4. **"Hey Andy, show me the room."** Andy looks across the room five times; SAM 3.1 marks your things in each look, and
   **MapAnything** (Meta's 3D model) turns the looks into the room's shape, joined by the head's own measured angles,
   on the computer beside the robot (about 1 s for all five). The TV draws it in 3D, turning slowly: dots for the shape,
   never a colour or a picture, your things as pins with how far each is. It's gone from the TV after two minutes and
   never saved; watched things get their place and distance, so the next "where are my keys?" is one look. About 35 s
   on the robot.
5. **Andy notices.** While Andy keeps an eye on your things and you're in view, it holds still between turns and
   watches in 4-second clips. Where something moved, **V-JEPA 2** (Meta's video world model) judges the clip on the
   computer beside the robot: put down, or picked up? A watched thing put down gets its new place in Andy's memory, and
   the TV says "Noticed: your keys, put down". Nothing moving, or the picture moving because Andy's head did: nothing
   is asked. On the robot with nobody there, 6 of 6 clips asked nothing; forced onto an empty clip, V-JEPA 2 gave
   "put down" 0.004 to 0.04 (it acts at 0.5). Not yet tried with a person putting something down.
6. **"Hey Andy, what happened to my keys today?"** Andy's memory of a watched thing is a story, not a dot: each place
   records how Andy knew it (found in a search, seen in passing, put down in view, the room scan) and when it was
   picked up, and the TV draws the day as a timeline. **"Where do I usually leave my keys?"** "Usually on the desk,
   behind the keyboard: 4 of the 6 places I've seen them." When the last place is empty, Andy looks at the usual one
   next, before sweeping the room ("Right where you usually leave them"). Words and directions, never a picture; the
   agent has both as tools. On the robot: "Usually on the desk, next to the phone stand: 3 of the 8 places I've seen it."
7. **An agent plans the search when you say where or which.** "Behind you, on the left" or "the blue one" goes to an
   agent: Muse Spark through the Meta Model API, or Muse Glimmer on the computer beside the robot, so the robot keeps
   working with no internet. A plain "where are my glasses?" uses a fixed sweep, which needs no model to plan.
8. **"The blue mug next to the laptop."** When there are look-alikes, Glimmer compares them and picks the one you
   described. A picture of your glasses on the TV isn't mistaken for your glasses.
9. **"Hey Andy, follow the mug."** Andy keeps its eyes on a thing as you move it around: SAM 3.1 finds it about twice a
   second on the computer beside the robot, and past the head's reach the base turns. Say "stop" when you're done.
10. **"Hey Andy, I'm going out."** Andy looks again where it last saw the things you asked it to keep an eye on, turns and
   points at any still here ("Your keys are still here, on the desk"), says which it didn't see (so they're probably
   with you), reminds you of the next reminder, and, looked up by Muse Spark while the robot was checking, whether to
   take an umbrella. 7 to 8.5 s with the robot simulated, 37 to 42.5 s on the robot; the TV shows the checklist.
11. **"Hey Andy, let's play the cup game."** Hide a ball under one of a few cups and shuffle them. Andy records the
   shuffle, then replays it through SAM 3.1's Object Multiplex on the computer beside the robot, which tracks every
   cup at once, so identical cups keep their own identities as they cross. Andy points at the cup with the ball, the TV
   draws each cup's path, and Andy watches the reveal and keeps score.
12. **"Hey Andy, this is my mug."** Hold it up and turn it; Andy learns it by sight. Later, "where's my mug?" skips
   anyone else's. What it looks like is kept as numbers on the computer beside the robot (DINOv2, Meta's open image
   model, plus a colour fingerprint, over SAM 3.1's mask of the mug alone), never a picture. "Forget my mug" deletes it.
13. **"Hey Andy, show me the weather radar on the TV."** Muse Spark's web search picks the page, a clean browser on the
   computer beside the robot opens it (no sign-ins, no downloads), and Muse Spark's computer use brings what was asked
   into view; the TV shows each step, with a dot where Andy clicks. "Scroll down", "go back". Code reviews every action
   before it runs: nothing personal is typed, and a sign-in or payment page ends it. Screenshots of web pages go to the
   cloud; the camera never does, and the TV's privacy receipt says which went.
14. **"Hey Andy, draw me a lighthouse at dawn."** Muse Image makes the picture from your words; it shows on the TV and is
   saved to your Pictures folder to print or share. "Make it sunset" changes it. **"Draw me a map of my things"** paints
   where the things Andy keeps an eye on were last seen, from words only (what each is near, and which way), labelled
   large: a drawing from memory, not a photo.
15. **"Hey Andy, what am I holding?" / "What's on the table?"** Andy looks (at your hands, found with SAM 3.1, or down
   at the table) and Glimmer says what it sees, on the computer beside the robot.
16. **"Hey Andy, what's that?"** (while pointing) Glimmer sees what you're pointing at, SAM 3.1 finds it, and Andy points
   at it too: "You mean the lamp?" On public photos Glimmer named the thing in 4 of 6 and imagined none; not yet tried
   with a person in the room.
17. **"Find my glasses, and remind me at 5 to clean them."** More than one thing at once goes to an agent: Muse Spark
   (or Glimmer, offline) gets all of Andy's abilities as tools (find, follow, look and tell, keep an eye on, forget,
   what it remembers, reminders, pictures, look up, show on the TV) and does them in order. **"Good morning, Andy"** (the first of the day) gets a short briefing:
   the weather where you live, today's reminders, and where your things are.
18. **"Speak up", "speak more slowly", "say that again", "move less", "be quiet for an hour."** How Andy speaks and
   moves is set by voice and remembered; while it's quiet, Andy starts nothing of its own. Reminders can be daily
   ("every morning at 8").
19. **"Oye Andy, habla español."** Andy hears and speaks Spanish: Meta's Omnilingual ASR is told to hear Spanish, Meta's
   SeamlessM4T v2 speaks it, and Muse Glimmer translates in between, on the computer beside the robot (about 0.5 s
   a sentence), so the abilities work in Spanish too (41 of 41 written requests reach the right one) and the person's words stay home. Saying it's an AI, the crisis reply (988 has
   help in Spanish) and Andy's short phrases are written by hand, never machine-translated. "Speak English" switches
   back; it's remembered.
20. **Talk to it.** "Hey Andy, where are my glasses?" Andy turns towards your voice, then looks. Hearing (Meta's
   Omnilingual ASR) and speaking (Meta's SeamlessM4T v2) run on the computer beside the robot. **Every model Andy
   runs is Meta's**, as the hackathon's rules ask.
   **How to call it: "Hey Andy".** Andy is the robot's name; HeyAndy is the company and how you call him, as "Hey
   Meta" and "Hey Google" are. "Hey Andy" is three syllables to the name's two (wake phrases of about three syllables are
   recommended, and short single words wake by accident more often); speech-to-text often hears a lone "Andy" as "and";
   and "Andy" is a person's name in many homes (Amazon's "Alexa" became a hard name for children to carry). Plain
   "Andy" still works, and follow-ups need no name; in a home with someone called Andy, "Hey Andy, only answer to 'Hey
   Andy'" makes it so ("answer to Andy too" undoes it; it's remembered). In Spanish, "Oye Andy".
21. **Ask from any room, on your phone** (opt-in: `--remote`). "Hey Andy, connect my phone" puts a web address and six
   numbers on the TV for three minutes; the phone that types them is paired. From the front door or the kitchen, tap
   "Where are my keys?": Andy finds and points in its room and says it there, and the phone follows it live (looking,
   pointing) and shows the find: the picture with SAM 3.1's outline, how long, how far, and the privacy receipt. Only
   devices on the home network, nothing at all until paired (codes end after three minutes or five wrong tries), only
   each phone key's SHA-256 kept, never asked by another name or from another site's page; "forget my phones" removes
   them. Tried on the robot from a phone-sized browser: paired, asked, and the keys found in 10.6 s on the phone.
22. **Pictures from your home never leave it.** SAM 3.1 (open weights), DINOv2 and Glimmer see the camera on the
   computer beside the robot, and so do your voice and Andy's. Muse Spark in the cloud gets words (labels, directions,
   plan steps, questions), plus screenshots of a web page you ask to see on the TV; Muse Image gets words. The TV's
   privacy receipt shows exactly what went, every turn. **"Hey Andy, what did you send to the cloud today?"** adds up the
   day's receipts on the computer beside the robot (so asking sends nothing): "Today, 21 of your 24 requests stayed in
   this house. For the other 3, I sent 68 words to Muse Spark..." Only the counts are kept, in memory, never the words.
   One switch is the exception, for filming only: `--staged-scene`, in a staged room with nobody in it, sends the camera's
   pictures to SAM 3.1 through the Model API, and the TV and the receipt say so every time.

## How it works

![What runs in the house and what goes to the cloud: the robot and the TV in the room; on the computer beside the
robot, a crisis check before any model, hearing and speaking, SAM 3.1 and DINOv2 for seeing, Muse Glimmer for
thinking offline, Andy's checked tools, and the web with Prompt Guard 2; in the cloud, Muse Spark gets words and
screenshots of web pages asked for, and Muse Image gets words only](docs/images/architecture.svg)

## Built during the event, and what came before
**This repository was started after the kickoff** (October 26, 2026, 12 PM ET) and holds only work done during the event.

**What existed before:**
- **Our own earlier object-finding prototype,** built before this event: **none of its code is in this repository,
  and nothing here imports it.** The search, memory, voice, agents and screen here were all written during the event,
  on Meta's models.
- **Third-party open source**, used under its licences: Pollen Robotics' Reachy Mini SDK and daemon, simulation scene,
  published camera calibration and recorded-emotions library (Apache-2.0); llama.cpp; Meta's `meta-sam-parser`, `sam3`,
  `map-anything` and `omnilingual-asr` code; Playwright and Chromium (the web on the TV); the Atkinson Hyperlegible
  Next and Mono typefaces (SIL Open Font License, `heyandy_meta/screen/fonts/OFL.txt`).

**What's new here,** all built during the event (the day-by-day record: [docs/research.md](docs/research.md)):
- **On the Reachy Mini Lite:** a closed-loop adapter (with apps/andy_finder, the only code that imports Pollen's SDK). The head falls short and
  sags, so it reads the pose back, corrects once, and every frame carries the measured direction; the base turns past
  the head's reach. Body language in a 50 Hz loop: breathing, listening, thinking, moving with its own words, a
  found-wiggle; it keeps its eyes on the person. At calm moments a feeling of its own from Pollen's recorded emotions library
  (Apache-2.0; moves, not a model): grateful for a thank-you, welcoming for good morning, an oops after a miss, a wave
  goodbye; never during a search or a point.
- **Meta's open weights on our own hardware:** SAM 3.1 served locally (several things per frame, and Object Multiplex
  tracking every cup at once), Muse Glimmer on llama.cpp (answering straight away for picture checks and translation),
  Omnilingual ASR (English and Spanish), DINOv2 (knowing the person's own things by sight), MapAnything (how far away a
  found thing is, from one camera frame: metric depth, about 0.2 s; and the room in 3D from five looks, about 1 s), V-JEPA 2 (Meta's video world model: noticing a watched
  thing put down or picked up), SeamlessM4T v2 (Andy's voice), Llama Prompt Guard 2 (reading each web page before the
  cloud model sees it), Llama Guard 3 (a second crisis check); with
  `scripts/verify_open_weights.py` proving the served Glimmer file is Meta's.
- **The search:** SAM 3.1 masks become head angles; a sweep (middle first), an early closer look at a confident
  sighting, a confirmed centred look before any point; Glimmer's picture check skips a thing on a TV or in a photo;
  close names in one request ("cup" also finds the mug). **After pointing, Andy checks the point landed:** one more
  frame measures how far the thing is from the middle of the view (correcting the aim past 3 degrees, at most twice), the TV shows it,
  and Andy says what it passed over on the way ("The other mug isn't yours").
- **Agents that plan the search with the robot's tools:** Muse Spark online, Muse Glimmer on this computer, with the
  same checked tools (named views and numbered places, never motor values), ten looks at most, no repeat looks, and
  Andy's words written from the tools' results, never the model's.
- **Following:** "Hey Andy, follow the mug": the eyes follow it as it's moved, about 2.4 frames a second.
- **Memory with a history, in words:** an opt-in idle glance notes where chosen things are; Glimmer describes each new
  place by what's near it ("on the desk in front of the monitor, behind the keyboard"), and Andy notes when a thing
  moved. "When did you last see my keys?" is answered from memory without moving. Never a picture.
- **Voice on this computer, all Meta's:** Omnilingual ASR hears; SeamlessM4T v2's speech half speaks (speaker 51, a
  man's voice), chosen by ear from five versions played on the robot's own speaker: slowed 8%, without rumble, the
  consonants brought forward (6 dB around 3 kHz) and never clipped; numbers, times and units become words first
  (Meta's MMS-TTS is wired in too); the robot's microphone array (and the voice's direction),
  "Andy" as the wake word with its common mishearings, answers spoken sentence by sentence.
- **Reminders delivered in person,** with Andy's questions taking the next answer.
- **New abilities:** the cup game (SAM 3.1 Object Multiplex), "this is my mug" (DINOv2 and a colour fingerprint, kept as
  numbers), "I'm going out" (pointing at what's still here, the weather looked up at the same time), "what's that?"
  (looking where the person points), the web on the TV (Muse Spark's computer use, every action reviewed in code), a
  map of where things are (Muse Image, from words), Andy in Spanish (hearing, voice, TV and every ability), and an
  agent that plans requests with several parts over the everyday abilities (finding, following, looking, keeping an
  eye on, reminders, pictures, looking things up, the web).
- **Muse Spark** for web answers with their sources (US units, only the final answer spoken) and harder conversation;
  **Muse Image** for pictures from the person's words, shown on the TV and saved.
- **Safety in code:** "I'm an AI" at the start and every three hours; a crisis reply with the 988 line before any other
  model sees the words (a word list, then Llama Guard 3 on this computer) ([docs/crisis-protocol.md](docs/crisis-protocol.md)); no false promises (a chat reply that claims an
  action is replaced); speech not for Andy is dropped; a hard cap on Model API spend.
- **The TV page,** read-only and on this computer, and the same page as a Hugging Face Space on sample data.
- **Scorecards:** the search, simulated (fixed sweep, Glimmer and Spark planners, seeded rooms); the agent (12
  multi-part requests); Spanish (41 requests, written and spoken); and a physical one, built and waiting to be run.

## Run it
```bash
uv sync --extra dev && uv run pytest -q   # no network calls: the model clients are tested against stand-ins
uv run python -m heyandy_meta             # talk to Andy by keyboard, in a pretend living room; TV at 127.0.0.1:8765
```
**On the robot computer, everything comes from this repository** (Ubuntu, two 24 GB NVIDIA GPUs, the Reachy Mini Lite
on USB; the steps download Meta's open weights from their public pages, so accept the gated ones on Hugging Face first:
SAM 3.1, Llama Guard 3, Llama Prompt Guard 2):
```bash
sudo usermod -aG dialout,video,audio "$USER"      # the motor port, the camera, the sound card; then log in again
scripts/setup-robot.sh          # GStreamer's webrtc plugin for the robot's camera, Pollen's daemon, the emotions library
scripts/setup-local-models.sh   # Muse Glimmer (llama.cpp), SAM 3.1, DINOv2, Prompt Guard 2, Llama Guard 3, the voice
scripts/setup-depth.sh          # MapAnything
for u in deploy/heyandy-*.service; do systemctl --user link "$PWD/$u"; done
systemctl --user enable --now heyandy-glimmer heyandy-sam heyandy-voice heyandy-guard heyandy-depth heyandy-app
uv run python scripts/preflight.py --cloud        # must end READY
```
The services: Glimmer and the voice on GPU 0; SAM 3.1, DINOv2, the guards, hearing and MapAnything on GPU 1; Pollen's
daemon (`heyandy-robot`) and Andy itself (`heyandy-app`). Before a demo, `scripts/preflight.py` checks everything
answers (about a minute, no camera). Muse Spark is used when `MODEL_API_KEY` is set in `~/.config/heyandy-meta/env`
(chmod 600) and `HEYANDY_PAID_CALLS=1`; spend stops at a hard cap of $140.

## Layout
```
heyandy_meta/app.py        one turn: what was asked, what the robot does and says; `python -m heyandy_meta` runs it
heyandy_meta/companion/    request rules, reminders, facing the person, answers with sources, AI disclosure, crisis protocol;
                           the cup game, the web on the TV, Spanish, pictures, following
heyandy_meta/finder/       the search, from a SAM 3.1 mask to where the head looks; Glimmer's picture checks; names
heyandy_meta/agent/        the search tools and the planning loop (Muse Spark online, Muse Glimmer on this computer)
heyandy_meta/memory/       where watched things were last seen, the idle glance, and the person's own things by sight
heyandy_meta/voice/        listening for "Andy", cutting speech into turns, Andy's voice
heyandy_meta/robot/        the body interface, the Reachy Mini adapter (Pollen's SDK), body language,
                           and a simulated room for tests
heyandy_meta/screen/       the TV page
heyandy_meta/models/       the model clients: Muse Spark (Model API), Muse Glimmer (and its straight-to-the-answer call),
                           SAM 3.1 (both on this computer)
heyandy_meta/router.py     who answers a turn: the device or the cloud
apps/andy_finder/          a slim Reachy Mini app for everyone: find and point, from the dashboard
                           (SAM 3.1 on the computer if it's there, else through the Model API: then camera pictures go)
heyandy_meta/network.py    whether the cloud is reachable right now
heyandy_meta/budget.py     the hard cap on Model API spend
local/                     SAM 3.1 (finding, /track for the cup game), DINOv2 (/embed) and Prompt Guard 2 (/guard);
                           MapAnything (how far, depth_server.py); hearing and speaking; all served on 127.0.0.1 only
evals/                     the scorecards (search simulated, agent, Spanish, the privacy audit; physical, to run) and
                           their results
scripts/, deploy/          setting up and running the models and Andy on this computer; the screen on sample data
config/                    config.example.yaml (no secrets)
docs/                      the hackathon's rules, research, the video plan, open weights
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
- **the day's privacy,** when asked: how many requests stayed in the house, and what went to which model;
- **captions of Andy's words** (never the person's).

"Hey Andy, what can I ask?" opens a guide. Frosted panels over colour that follows the time of day, a calm night mode, every
text colour at least 7:1 against its panel (tested), and the Atkinson Hyperlegible typeface (large, high-contrast type) served
by Andy itself: the TV asks nothing of anyone outside the house.

**Andy's sounds:** Andy answers before it speaks. A quick rising chime the instant it hears its name
([listen](docs/sounds/andy-heard.wav)); a bright run to the octave as a find lands, with the TV's Reveal, before "There
it is!" ([listen](docs/sounds/andy-found.wav)); a gentle falling bell before a reminder, to reach you across the room
([listen](docs/sounds/andy-reminder.wav)); one soft note when it notices a watched thing put down
([listen](docs/sounds/andy-noticed.wav)). All in C major, one struck, marimba-like timbre, a little below its voice; made
from plain maths on the computer beside the robot (`heyandy_meta/voice/earcons.py`, no model). Never before the crisis
reply; none of its own while it's asked to be quiet, except a reminder, which was asked for. `HEYANDY_SOUNDS=0` turns
them off.

**Ambient Andy:** after a quiet minute the TV becomes Andy's face (HeyAndy's own mark) over a large clock. It blinks, glances
about, and **looks at you**: when Andy's camera finds a person, in a conversation or while it watches over your things,
the face's eyes turn towards them (a direction, never a picture). The next reminder and what Andy keeps an eye on sit
below; the colours follow the time of day, porcelain on night blue after dark. A word, a search or a reminder and the
TV wakes. (`?ambient=now` shows it at once, for filming.)

![Ambient Andy: the TV's face over a large clock, the next reminder and what Andy keeps an eye on (sample data)](docs/images/tv-ambient.png)

**The Reveal:** the moment a find lands, the TV takes over for five seconds, like a film: the room goes dark, a spotlight
opens on SAM 3.1's own outline of the thing, the shot pushes in while the outline draws itself, and the thing's name
rises with three counters (the seconds it took, the degrees off target its camera measured, how far away). Then it
settles into the card below. Only for a find made just now; still, without the push, for anyone who prefers less motion.

![Found: the picture with the mug outlined; the time, how far off target the point landed and how far away; the models used](docs/images/tv-found.png)

| | |
|---|---|
| ![Finding: what Andy sees, live, the candidate outlined by SAM 3.1](docs/images/tv-finding.png) | ![An answer with sources](docs/images/tv-answer.png) |
| ![At night](docs/images/tv-found-night.png) | ![What can I ask?](docs/images/tv-help.png) |
| ![A picture from your words, by Muse Image](docs/images/tv-drawing.png) | ![What Andy remembers: a floor plan in feet, from MapAnything's distances](docs/images/tv-memory.png) |
| ![The room in 3D: its shape from MapAnything over five looks, your things pinned with their distances (a made-up room for the demo)](docs/images/tv-room.png) | ![Andy waiting: every model it runs is Meta's, and where each runs](docs/images/tv-idle.png) |

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
| Behind the robot, with a hint | 92, 0 wrong, 7.1 looks | **20**, 0 wrong, 4.0 looks | **18**, 0 wrong, 4.2 looks |
| A picture of it on the TV too | 94, 0 wrong | 19, 0 wrong | 19, 0 wrong |
| Not there at all | 100 said so | 20 said so | 20 said so |
| Two look-alikes, "the blue one" | 80, **20 wrong** | **18**, 2 wrong | **18**, 1 wrong |
| Planning time (model only; not counting "not there") | none | 8 to 13 s | **6 to 8 s** |

Pointing error (median, with 1.5 degrees of assumed head noise): about 1.7 degrees, inside the 6 degree target. Every
column was rerun on October 30 on the final code, and Glimmer's again on October 31 after the search tools' colour
fixes, with the same results (a look now counts the check after pointing; Glimmer runs without its
drafter, so it plans more slowly; the October 28 runs are kept as `*-oct28.json`). Two rounds of fixes came from this scorecard, and the earlier runs are
kept:
- **October 27 (no repeat looks; compare points at once):** Spark went from 12 look-alikes and 14 TV cases to 16 and 20;
  Glimmer's look-alikes went from 20 to 17 (`*-before-tool-fixes.json`).
- **October 28 (a colour or "next to" is for compare, and when the person said which one, nothing is pointed at before
  compare has picked):** look-alikes went to 19 (Glimmer) and 18 (Spark) (`*-before-colour-fix.json`). Spark's three
  new misses (behind 2, TV 1) were all its ten looks spent trying other names where the thing wasn't.

The wrong look-alikes left (Glimmer 2, Spark 1) come from the simulation's own stand-in for Glimmer's picture check, which
matches words and mixes up "the big one" and "the small one". With 20 rooms a scenario, a point or two either way is
noise. Results: `evals/results/`.

**On the robot** (Reachy Mini Lite, 2026-10-27): a cup found in 7.5 s and a keyboard in 8.2 s, the screen check included
(7.1 s for the keyboard once Glimmer's picture check went straight to its answer; research.md, 24);
pointing within about 3 degrees after the head's correction, as its motors report it.

**Start to finish, on the robot** (2026-10-31, requests typed to Andy on the Lite with its voice on, nobody in the room;
from the request to the end of Andy's spoken answer): a plain find 19 to 25 s ("Let me look.", the sweep, the check, the
point, how far, the answer), then 13 to 19 s once Andy started looking while saying "Let me look." and made the next
sentence while one played; "the blue cup" 17.6 to 23 s, planned by Muse Spark or Glimmer; "the red cup" with only a blue
one there, 40 to 50 s, and no point; "where are my glasses and what time is it?" 30.5 s (the agent, 2 steps); "I'm going
out" 37 to 42.5 s (two places looked at again, and the weather); the weather radar on the TV 30.9 s; the map of things
39.1 s; the time, from the clock, 2.5 to 4.4 s; in Spanish, a find 20.6 to 25.5 s. Slower than the simulated figures
above, which leave out the robot's moves and Andy's voice.

**Measured by Andy's own camera** (`evals/unattended.py`; the robot alone in the room, nobody checking what it pointed
at, so this measures the aim and the reliability, not the finding). On October 30 the check after pointing showed the
head sags about 4 degrees after its pointing nod, so Andy corrects its aim from what the frame shows (at most twice): 34
searches for a monitor, a keyboard and a chair, 34 pointed, a median 5.2 degrees off, but up to 21 where the base
turned. On October 31, on a table with keys, glasses, a watch, two keyboards and a cup, the numbers found why: the
daemon takes and reports the head's direction **in the room**, the base's turn already in it (the same view with the
base at 0 and at -30 degrees), and Andy had added the base's turn again, so past 30 degrees it faced only 30 degrees
round. Fixed (and SAM 3.1 is asked for "bunch of keys": asked for "keys" it outlined all 28 keys of a keyboard). After
the fix, `unattended-20261031-0924`: **20 of 20 pointed, none failed, the thing seen after every point, a median 4.3
degrees from the middle of the view, 8.7 at worst** (13.7 before the fix on the same table), a median 12.0 s each, the
check included; on the final code (the lens's own focal length, which reads the same offset about 6% larger, and quicker
small corrections), `unattended-20261031-1106`: 15 of 15, a median 5.2, 8.3 at worst, 11.7 s (the same 15 with the old,
slower corrections: 6.0 and 11.2, so run to run the median moves about a degree). **Turning far round, for real:** a sofa
at Andy's left, where the base turns 55 degrees under the head, was pointed at 8 of 8, a median 2.8 degrees off,
1.21 to 1.38 m (`unattended-20261031-1212` and `-1213`, at 84 to 85 degrees); before the fix the head never faced past
30. **Distances repeat within a run:** the same keyboard read 0.92 to 1.00 m and the chair 1.28 to 1.35 m
from five starting poses on October 30; on the 31st, four searches each, the keys 0.59 to 0.64 m, the keyboard 0.65 to
0.71, the cup 0.92 to 1.04, the glasses 1.01 to 1.20 (MapAnything; things were moved between runs, and distances aren't
yet calibrated against a tape measure, which MapAnything reads about 13% short on public test photos, so Andy says
"about").

**The room in 3D, and the robot's own lens** (2026-10-31, on the robot; `evals/room.py`, `evals/lens.py`): MapAnything's
depth for each of five looks, each pixel's ray from Andy's own camera, turned by the head's measured angles. Letting
MapAnything join the looks itself, a watch read -30 and -41 degrees from two looks (1.3 times too wide); this way, over
three scans (`room-20261031-1129`), a thing seen from two or three looks agreed to a median 0.9 degrees, small things
within 2.3 (a keyboard, half out of some looks, 4.9 to 7.6), and scan to scan every thing landed within 1 degree and 8
cm; about 13 s for the five looks, 1.0 s for MapAnything. Andy measured its own lens too: a watch, a cup and glasses
each centred, then seen from 27 head angles up to 42 degrees off. The published focal length (1116 px at 1080p) fits
worse than the one measured, 1054 and 1049 px in two runs (`lens-20261031-1128`, 78 sightings: 2.95 degrees RMS against
3.41, head noise included); out near the edges of the view the published one put things up to 4.7 degrees out. Andy uses
1054: the sweep's first guesses, merging one thing seen in two views, and the room. **Noticing** (`evals/notice.py`,
`notice-empty-20261031-1130`): 10 clips of the empty table with the head still, 0 noticed; V-JEPA 2 asked once (1.6% of
the picture changed), "put down" 0.015.

**The agent** (`evals/agent.py`, 12 requests with more than one part, simulated room, real models): Muse Spark 12 of
12, Muse Glimmer on this computer 12 of 12; a request counts only if everything asked happened. The first run was 6 of
12; what failed and what changed is in `docs/research.md`, section 26.

**Spanish** (`evals/spanish.py`, 41 requests, several ways of asking for each ability): written, 41 of 41 reach the
right ability; said by Andy's voice (Meta's SeamlessM4T v2) and heard by Omnilingual ASR, 34 of 41 (hearing slips on the
synthetic voice; 40 of 41 with the earlier non-Meta voice, before every model had to be Meta's). That's after two translation rules this scorecard showed were needed ("vaso" is a cup, and
a question stays a question when speech-to-text drops the question marks): 38 and 37 before. Glimmer translates each in
a median 0.49 s (at most 0.71), on the computer beside the robot.

**The privacy audit** (`evals/privacy.py`, 2026-10-28): a day of 21 requests (the morning briefing, finding,
reminders, conversation, the web on the TV, pictures, going out, Spanish, a crisis) with the real models, while every
HTTP request the program made was recorded on its way out, and the simulated camera took real pictures. **21 of 21
turns pass:** none of the 24 camera pictures reached the cloud (rerun Oct 30 on the final code); the one image that did was a web page's screenshot, on
its receipt; every word from the home that was sent was on its turn's receipt (40 of 43 pieces word for word; the other
3 are the person's words inside Andy's own instructions, for a picture and the web); the crisis words reached no model
at all. 11 of the 21 turns sent nothing. With
the network off, the same day sent nothing to the cloud, and Andy answered every turn.

**The cup game, tracking only** (SAM 3.1 Object Multiplex on an RTX 3090, synthetic shuffles of three identical cups, 4
swaps of 0.8 s each; `docs/research.md` sections 18 and 29): about 4 frames a second through the server, so a 4-second
shuffle replays in about 10 to 13 s.
At the camera's 10 frames a second it picked the right cup in 3 of 5 runs with the detection batches that fit beside the
safety models (4 of 5 with larger ones); at 5 frames a second it lost the cups in all 4. Not
yet scored with real cups. The physical scorecard (`evals/physical.py`) comes next.

## What doesn't work yet
- **Not yet tried on the robot with real things or a person:** the cup game (tracking measured on synthetic shuffles;
  identical cups crossing fast can still swap), "this is my mug" (measured on the robot's camera with things seen from
  other angles, not with two mugs), "what's that?" (Glimmer measured on public photos: 4 of 6), and "I'm going out"
  (the robot simulated). Each has a founder's test written down.
- **The Model API sometimes returns `404 model_not_found` on new accounts** (reported by other participants; Meta is
  investigating). Calls retry twice, then the robot answers on the device.
- **The physical scorecard isn't done yet.** On the robot Andy has found real things, delivered a reminder in person,
  and held conversations; the scored runs come next
  (`docs/research.md` sections 8 to 11).
- **English and Spanish** for now: Omnilingual ASR can hear far more languages; SeamlessM4T v2 speaks 35, and adding one
  is a few hand-written phrases. While Andy speaks Spanish the TV is in Spanish too (labels by hand, Andy's
  own words translated by Glimmer). Spanish is scored on written and synthesised speech; not yet with a person.

## Licence
Apache-2.0, for this repository's own code. **The models keep their own licences:** Muse Glimmer, SAM 3.1, MapAnything,
DINOv2, V-JEPA 2 (MIT) and Omnilingual ASR as published by Meta; Llama Guard 3 and Llama Prompt Guard 2 under the Llama 3.1 and Llama 4
Community Licenses (**Built with Llama**); SeamlessM4T v2 and MMS-TTS, Andy's voice, under CC-BY-NC 4.0, so this is a
non-commercial demonstration and a product would need a voice licensed for commercial use. The web page in
`docs/images/sample-web.jpg` is Wikipedia's "Banana bread" (CC BY-SA 4.0). The HeyAndy name and logo (the face and the HeyAndy lettering on the TV page) are HeyAndy, Inc.'s
marks (HEYANDY™, a pending US trademark application) and aren't licensed under Apache-2.0. `meta-sam-parser`, a dependency, is under Meta's SAM License.
