---
title: Andy Finder
emoji: 🔎
colorFrom: green
colorTo: yellow
sdk: static
pinned: false
license: apache-2.0
short_description: Reachy Mini finds what you've lost and points at it (SAM 3.1)
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Andy Finder

Type what you've lost ("glasses", "keys", "the remote") and Reachy Mini looks around the room, finds it with Meta's
SAM 3.1, turns to it and nods. If it can't see it, it shakes its head and says so. A small piece of
[HeyAndy](https://github.com/AndyDM9/heyandy-meta), a robot for people who live at home, built for Meta's Global AI
Developer Hackathon.

**Where the camera pictures go, said plainly:**
- **On your computer** (best): if SAM 3.1 runs on this computer at `http://127.0.0.1:8090` (`local/sam_server.py` in
  the HeyAndy repository, with an NVIDIA GPU), every picture stays here.
- **Otherwise, Meta's Model API:** with `MODEL_API_KEY` set, each look sends one camera picture to SAM 3.1 through the
  Model API, and Meta keeps it under its normal terms. Use it in a room you're happy to share. The app's page shows
  which one is in use.

Install it from the Reachy Mini dashboard (Applications, Discover Apps), or `pip install` this folder and start it.
