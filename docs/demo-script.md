# The 3-minute video (draft)

Judged on impact (30%), use of Meta's models (25%), technical depth (20%) and the demo (25%). One uncut take carries
the demo; the numbers carry the depth. Filmed on the Reachy Mini Lite in a staged room (no other people, nothing
personal in view). The TV page is screen-recorded at the same time.

| Time | On screen | Said, and what happens |
|---|---|---|
| 0:00–0:06 | Title card | **Required first line (FAQ):** what existed before (a Reachy Mini; our own earlier object-finding prototype) and that everything shown was built this week on Meta's models. *(the founder's exact words)* |
| 0:06–0:16, a caption over the problem shot | One plain line, as the organizers asked (Oct 30 ruling): | "Andy gives no health advice. It finds things, remembers where they are, and reminds you of what you asked." |
| 0:06–0:16 | A person patting their pockets | The problem in one line: the same few things go missing every day, and a camera that streams your home to the cloud is a camera most people won't have. |
| 0:16–0:55 | **The uncut find**, robot and TV side by side, badge "autonomous · uncut · 1× speed" | "Andy, where are my glasses?" Andy turns to the voice, "Let me look", sweeps, **skips the glasses on the TV**, looks closer and points: "There they are! I see your glasses, to my right, about 5 feet away. Not the picture of one on the screen." The TV, filmed beside the robot: **while it looks, each view live with SAM 3.1's outlines on every candidate**; then the found picture with three large figures (seconds to find it, degrees off target checked by its camera, feet away from MapAnything) and the models used. |
| 0:55–1:12 | **Follow the mug** | "Andy, follow the mug." The person slides it around the table; Andy's eyes stay on it, the base turning past the head's reach. "Stop." |
| 1:12–1:32 | **Several things at once** | "Andy, find the cup and remind me in two minutes to call Sam." The agent's steps appear on the TV; the robot points; "Your reminder is set." |
| 1:32–1:46 | **Unplug the network** | The TV says Offline; "Andy, where's the remote?" still works: SAM 3.1, Glimmer and the voice are on the computer beside the robot. "Pictures and voice stay in your home." |
| 1:46–2:04 | Quick cuts | **"Andy, show me the room"** (five looks, then the room's shape in 3D turning on the TV with your things pinned: MapAnything; about 35 s, so a labelled time cut to the TV) · "What am I holding?" (Glimmer says, locally) · "Draw me a lighthouse at dawn" (Muse Image fills the TV) · "Show me the weather radar on the TV" (Muse Spark's computer use, each click on the TV; about 31 s on the robot, a labelled time cut) |
| 2:04–2:16 | The reminder, two minutes later (a labelled time cut) | Andy finds the person, turns to them: "You asked me to remind you: call Sam." |
| 2:16–2:44 | The numbers and the models | The scorecard (simulated and physical, failures included), and every Meta model with where it runs: SAM 3.1, Muse Glimmer, MapAnything, Omnilingual ASR, SeamlessM4T v2 (the voice), DINOv2, Llama Guard 3 and Llama Prompt Guard 2 (and V-JEPA 2, if "Andy notices" is in) on our hardware: every model Andy runs is Meta's; Muse Spark and Muse Image in the cloud (words, and screenshots of a web page asked for on the TV). |
| 2:44–3:00 | Robot close-up | What's next (our own robot design, as a silhouette only) and one line on why HeyAndy. |

**The cup game, if it scores well with real cups:** it replaces "Follow the mug" at 0:55 to 1:12 and becomes the X clip.
"Andy, let's play the cup game": the ball goes under a cup, a slow shuffle, "Let me replay that" (a labelled time cut over
the replay), Andy points, the cup is lifted, and the TV shows every cup's path. It shows SAM 3.1's Object Multiplex
doing what finding frame by frame can't: telling identical cups apart as they cross.

**"This is my mug," if the founder's two-mug test goes well:** it fits the uncut find (0:16 to 0:55) instead of "the
blue one": "Andy, this is my mug" (held up and turned), then with a second mug of another colour on the table, "Andy,
where's my mug?" The TV lists each mug's likeness ("58% like yours: not yours", "91%: yours"). It shows a Meta open model
(DINOv2) and the privacy story in one line: "I keep what it looks like as numbers, never a picture."

**"Andy notices," if the founder's test 11 goes well** (`uv run python -m evals.notice --person`): after "keep an eye on
my keys", the person walks in and puts the keys down on the table in view; the TV says "Noticed: your keys, put down";
later, "Andy, where are my keys?" goes straight there in one look. It shows V-JEPA 2, Meta's video world model, doing
what a still picture can't: seeing an action. Leave it out if it misses more than it catches.

**Things can be anywhere round the robot now:** the sofa at 85 degrees to its left was pointed at 8 of 8. A thing to the
side or behind, with "I think it's behind you, on the left", makes the agent's moment (Muse Spark plans one look).

**The X clip (30 s, vertical, `make_film.py --shape vertical`):** the first second is the head turning to point; the
TV's live view and the three figures carry it without sound; one caption line: "Pictures never leave the house. Every
model is Meta's."

**Cards (ready in `film/`, not committed):** `card-open.png` (HeyAndy's signature and the required line on what was
pre-existing; replace the line with the founder's own words if they differ) and `card-end.png` (the signature, "Andy finds
what you've lost, and points at it.", every model Meta's, no health advice, the links). The TV wears the same signature.

## Filming day, step by step

1. **Preflight** (a minute): `uv run python scripts/preflight.py --cloud` must end with "READY". Anything listed as
   FAIL says what to do; most often `systemctl --user restart heyandy-app` and run it again.
2. **The room:** staged. Nobody else in view, nothing personal (letters, photos, a phone or screen with anything
   private on it). The things for the takes in place: glasses (and a picture of glasses on the TV), the blue mug and a
   look-alike, keys, the remote; three opaque cups and a small bright ball if the cup game is in.
   **Where to put things:** anywhere on the table in front of the robot. Since the head fix of October 31 (the base's
   turn had been counted twice), the camera-checked aim is a median 4 to 5 degrees, under 9 at worst, across the table, out
   to about 50 degrees each side (`unattended-20261031-0924` and `-1106`). Keys: a bunch of keys, not a single key, and not touching
   a keyboard.
3. **The TV:** Chrome full screen (F11) on `http://127.0.0.1:8765`. If Andy was speaking Spanish, "Andy, speak English".
4. **Cameras:** the robot and the TV side by side in one shot, 1080p, normal speed. Start the TV recording just before
   each take: `uv run --with playwright python scripts/record_tv.py --seconds 200 --out film/take1.webm --room-is-staged`
   (once beforehand: `uv run --with playwright playwright install ffmpeg`). Line it up with the camera footage in the
   edit: Andy's first word is an easy sync point.
5. **Takes,** in the storyboard's order. Speak at a normal distance, start with "Andy", and wait for Andy to finish.
   Something goes wrong: "Andy, stop", then the next take; if Andy stops answering, restart it (step 1's command, 20 s)
   and run the preflight again.
6. **Between takes:** nothing to delete on this computer (Andy keeps no pictures or audio); `film/` is never committed.
   Keep every take that's used, uncut, for the "autonomous · uncut · 1× speed" badge.
7. **After a good take** (a minute each, all on this computer): captions from Andy's own hearing, read and corrected by
   hand, then the piece with the captions and the badge burned in, the robot and the TV side by side:
   ```bash
   uv run python scripts/make_film.py captions film/take1.mp4          # -> film/take1.srt; fix any wrong word
   uv run python scripts/make_film.py burn film/take1.mp4 --tv film/tv-take1.webm --tv-offset 0.8 --out film/find.mp4
   uv run python scripts/make_film.py burn film/take1.mp4 --start 12 --end 42 --shape vertical --out film/x-clip.mp4
   ```
   `--tv-offset` is the second of the TV recording that matches the take's first frame. A piece across a time cut gets
   its own badge: `--badge "autonomous · 1× speed · two minutes later"`.

**Rules for filming:** no Meta logos; no music we don't own; subtitles burned in; no condition names and no health,
safety or loneliness claims; the people Andy is for are "people who live at home"; our own robot design is never
shown beyond a silhouette.

**For X (Most Viral):** the uncut find (or the cup game, if it's in) cut to 30 seconds, captions burned in, the same badge. Posted as soon as there's a good take: the prize counts engagement through November 8, and the post's link goes into the submission (`docs/rules.md`).
