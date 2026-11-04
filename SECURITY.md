# Security

Andy is a robot with a camera and microphones in someone's home, so a weakness here matters more than in most
software. Please report one privately: on this repository's **Security** tab, **Report a vulnerability** (GitHub's
private reporting). Please don't open a public issue for it. We'll answer within a few days, and say when it's fixed.

## What Andy is built to keep

- **Pictures and sound stay in the home.** The finder, the picture checks, hearing and the voice all run on the
  computer beside the robot. No camera picture of a home goes to the cloud. The one exception is a staged room for
  filming (`--staged-scene`), and the TV says so while it's on. Only words go to the cloud (Muse Spark, and Muse Image for a drawing), and only while online.
- **Nothing listens beyond this computer.** Every service (the TV, the models, the voice, Pollen's robot daemon and its
  WebRTC signalling) binds to 127.0.0.1. The robot daemon's relay through Pollen's cloud is switched off
  (`scripts/robot_daemon.py`). The TV takes one setting, the language, and only from its own page: its key, its origin,
  JSON (`heyandy_meta/screen/server.py`).
- **Spend has a hard stop.** Paid calls need `HEYANDY_PAID_CALLS=1`, and `heyandy_meta/budget.py` refuses any call past
  the cap. Meta's own spend limit only sends an email.
- **Keys stay out of the code.** `MODEL_API_KEY` lives in `~/.config/heyandy-meta/env` (chmod 600).
  `scripts/release_check.py` searches the whole history for a key's value before each release.
- **Safety isn't left to a model.** Crisis and emergency replies are written by hand, in each of Andy's fifteen
  languages. No model answers a health question. See `docs/crisis-protocol.md` and `docs/system-card.md`.

## In scope

This repository's code, the services in `deploy/`, and the static Space built from it. Pollen's daemon and Meta's
models have their own maintainers. Tell us anyway if Andy's use of them opens a hole.
