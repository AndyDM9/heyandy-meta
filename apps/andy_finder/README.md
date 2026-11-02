---
title: Andy Finder
emoji: 🔎
colorFrom: green
colorTo: yellow
sdk: static
pinned: false
license: apache-2.0
short_description: Reachy Mini turns to your ringing phone, and finds what you've lost
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Andy Finder

**Lost your phone? Tap "Ring it", then call it.** Reachy Mini listens with its own microphones and turns, a step at a
time, until it hears the ringing straight ahead, then nods towards it: "It's ringing a little to my right, where I'm
looking." Nothing to set up: no key, no GPU, no internet; nothing is recorded (only how loud, how pure a tone and
which side, a tenth of a second at a time). With SAM 3.1 it then looks there and shows you the phone. A voice is
never taken for a ringing.

![Andy Finder after "Ring it": seen from above, each turn of Reachy's head, the side it heard the ringing on, and where it is](screenshot-ring.png)

And for anything else: tap what you've lost (glasses, keys, phone, remote, wallet, mug, watch) or type any thing, and Reachy Mini looks around
the room, finds it with Meta's SAM 3.1, turns to it and nods, then **checks its own point with its camera** and
corrects it once if it's more than 3 degrees off. The app's page shows what it sees as it looks (each view, every
candidate SAM 3.1 outlined, five views lighting up), then the find: a spotlight on the thing, which way it is, how long
it took, how sure SAM 3.1 was, and how many degrees off its camera measured the point. If it can't see it, it shakes
its head and says so.

**What HeyAndy measured on a Reachy Mini Lite, built in (0.3.0):** the camera's continuous autofocus hunts for seconds
after every turn of the head, and small things like keys went unseen, so the app focuses once on the table as it starts
(about 10 s) and holds it, then gives the camera its autofocus back when it stops; a frame is taken only once the
picture has caught up with the head (half a second); each pixel becomes a direction by its true ray (adding two angles
is off by several degrees at the frame's sides when the head looks down); after the nod the head is read back and
lifted (it sags about 4 degrees); and "keys" is asked as "bunch of keys" (asked for "keys", SAM 3.1 outlines every key
of a keyboard). On HeyAndy's robot (November 2): 13 of 14 points checked by the camera within 1.7 degrees, a median 1.1;
a find in about 5 s when the middle view sees it.

![Andy Finder after a find (a drawn sample picture)](screenshot.png) A small piece of
[HeyAndy](https://github.com/AndyDM9/heyandy-meta), a robot for people who live at home, built for Meta's Global AI
Developer Hackathon.

**Where the camera pictures go, said plainly:**
- **On your computer** (best): if SAM 3.1 runs on this computer at `http://127.0.0.1:8090` (`local/sam_server.py` in
  the HeyAndy repository, with a CUDA GPU), every picture stays here.
- **Otherwise, Meta's Model API:** with `MODEL_API_KEY` set, each look sends one camera picture to SAM 3.1 through the
  Model API, and Meta keeps it under its normal terms. At Meta's price ($2.50 per 1,000 images) a find costs about half
  a cent: two pictures when it's in the first view (one to find it, one to check the point), seven at most. Use it in a room you're happy to share. The app's page shows
  which one is in use, and shows a camera picture only while it looks and for two minutes after a find, held in
  memory, never saved.

Install it from the Reachy Mini dashboard (Applications, Discover Apps), or `pip install` this folder and start it.
