---
title: Andy's screen
emoji: 🤖
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
license: apache-2.0
short_description: The TV beside Andy, a tabletop robot built on Meta's models
---

# The TV beside Andy

**Andy** is a tabletop robot (a Reachy Mini Lite, for now) that finds what you've lost and points at it, knows your
own mug from anyone else's, keeps an eye on the things you choose, checks you have them when you go out, reminds you in
person, plays the cup game, shows the web on the TV, and speaks fifteen languages (Spanish, Mandarin, Tagalog, Vietnamese, Korean, Russian and more). It checks with its own camera that its point
landed, and says how far away the thing is. (The cup game, "this is my mug", "what's that?" and going out are built
and measured in simulation or on photos, not yet on the robot with real things.) It was built by **HeyAndy, Inc.** for Meta's Global AI Developer Hackathon (startup track, *Push the
Frontier*), on Meta's models, and **every model it runs is Meta's**: Muse Glimmer, SAM 3.1 (with Object Multiplex), MapAnything (how
far), DINOv2, Omnilingual ASR, SeamlessM4T v2 (its voice), Llama Guard 3 and Llama Prompt Guard 2 from their open weights
on the computer beside the robot, and Muse Spark and Muse Image through the Meta Model API. **Andy gives no health
advice.**

**It opens as a one-minute story:** eight chapters of the TV, each a real scene (you ask; it finds it, with the
Reveal; your room in 3D; identical cups told apart; before you go; Spanish; nothing leaves the house), then where to
go next. Pause, skip with the arrow keys, or "Explore every screen".

**Andy's eyes, on your own things** (`eyes.html`: "Try it on your own things" at the top, or the story's end): show
it something of yours once, then a photo of where it might be, and DINOv2, Meta's open image model, finds it, **running
in your browser**: your photos are read there and sent nowhere. It says "There's your mug" only when it's alike and the
same colour, asks "is it?" when it's close, and says when it doesn't see it. No photo to hand? Use our cup (The Met's
Open Access, CC0).

The TV itself is the robot's, the same page and rendering code as on the robot with each scene saved in advance, **on sample data**: no robot, camera
or keys are here (the one model that runs here is DINOv2, in Andy's eyes, in your browser), and the picture is drawn, not taken in a home. Pick a scene at the top: what Andy shows while
it searches (what its camera sees, every candidate outlined by SAM 3.1), what it found (how long it took, how far off
target its point landed, and how far away it is), your own mug told from another, the cup game (every cup's path
through the shuffle), going out, Andy in Spanish, a web page Andy opened, an answer with sources, a picture, what it remembers, the day's privacy
("what did you send to the cloud today?"), and "What can I ask?". The web page in "On the web" is Wikipedia's (CC BY-SA 4.0).
Nothing you do here reaches anyone else.

In a real home, pictures and voice never leave the house: SAM 3.1, Muse Glimmer and the speech models run on the
computer beside the robot, and Muse Spark only ever gets words (and, when you ask Andy to show something on the TV,
screenshots of that web page).
