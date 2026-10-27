# HeyAndy x Meta

**A tabletop robot that finds what you've lost, and points at it.** It's built on Meta's models for people who live at
home, starting with older adults. Entered in Meta's Global AI Developer Hackathon (startup track, *Push the Frontier*) by
**HeyAndy, Inc.**, a Delaware corporation ([heyandy.ai](https://heyandy.ai)). HEYANDY™ is the subject of a pending US
trademark application.

## What it does
1. **Ask "where are my glasses?"** The robot looks around the room.
2. **SAM 3.1 finds them.** Its mask becomes the head's angle. The robot looks closer, checks, and points.
3. **The TV shows the picture it saw them in,** with the mask drawn. The picture is kept in memory only, never saved.
4. **Muse Spark plans the search; Muse Glimmer works offline.** Muse Spark plans through the Meta Model API. Muse Glimmer
   runs on the computer beside the robot, so the robot keeps working with no internet.

## Built during the event, and what came before
**This repository was started after the kickoff** (October 26, 2026, 12 PM ET) and holds only work done during the event.

**What existed before:**
- **our earlier prototype** ([(not in this repository)](https://(not in this repository))): the founder's
  earlier robot, built before this event. Its finder uses a vision-language model. It is **not in this repository,
  and nothing here imports it.** Its published results are our *baseline*: we run it unchanged in its own repository and
  bring only its result files here, marked as pre-existing.
- **Third-party open source**, used under its licences: Pollen Robotics' Reachy Mini SDK, simulation scene and published
  camera calibration; llama.cpp; Meta's `meta-sam-parser`.

**What's new here, as it's built** (progress in [docs/build-plan.md](docs/build-plan.md)):
- **Model clients:** Muse Spark and SAM 3.1 through the Meta Model API, and Muse Glimmer locally.
- **A hard spending cap,** because Meta's Billing "spend limit" only sends an email.
- **SAM 3.1 masks turned into head angles,** and sightings merged across views.
- **Next:** the search itself, the Reachy Mini body, voice, object memory, and the before/after evaluation.

## Run the tests
```bash
uv sync --extra dev && uv run pytest -q   # no network calls: the model clients are tested against stand-ins
```

## Layout
```
heyandy_meta/models/   Muse Spark and SAM 3.1 (Model API) and Muse Glimmer (local) clients
heyandy_meta/finder/   from a SAM 3.1 mask to where the head looks
heyandy_meta/router.py who answers a turn: the device or the cloud
heyandy_meta/budget.py the hard cap on Model API spend
config/                config.example.yaml (no secrets)
docs/                  the build plan, the hackathon's rules, research
tests/
```

## What doesn't work yet
- **No live model call has been made yet.** The first paid calls wait for the hackathon credits.
- **SAM 3.1 frames are sent as data URLs.** That the API accepts them gets checked on the first call.
- **There is no robot body, voice or search loop yet,** and no measurements.

## Licence
Apache-2.0. `meta-sam-parser`, a dependency, is under Meta's SAM License.
