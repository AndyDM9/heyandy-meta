# The 3-minute video (draft)

Judged on impact (30%), use of Meta's models (25%), technical depth (20%) and the demo (25%). One uncut take carries
the demo; the numbers carry the depth. Filmed on the Reachy Mini Lite in a staged room (no other people, nothing
personal in view). The TV page is screen-recorded at the same time.

| Time | On screen | Said, and what happens |
|---|---|---|
| 0:00–0:06 | Title card | **Required first line (FAQ):** what existed before (a Reachy Mini; our own earlier object-finding prototype) and that everything shown was built this week on Meta's models. *(the founder's exact words)* |
| 0:06–0:16 | A person patting their pockets | The problem in one line: the same few things go missing every day, and a camera that streams your home to the cloud is a camera most people won't have. |
| 0:16–0:55 | **The uncut find**, robot and TV side by side, badge "autonomous · uncut · 1× speed" | "Andy, where are my glasses?" Andy turns to the voice, "Let me look", sweeps, **skips the glasses on the TV**, looks closer and points: "I see your glasses, to my right." The TV: the frame with SAM 3.1's outline, the plan, the timer, the models used. |
| 0:55–1:12 | **Follow the mug** (the X clip) | "Andy, follow the mug." The person slides it around the table; Andy's eyes stay on it, the base turning past the head's reach. "Stop." |
| 1:12–1:32 | **Several things at once** | "Andy, find the cup and remind me in two minutes to drink some water." The agent's steps appear on the TV; the robot points; "Your reminder is set." |
| 1:32–1:46 | **Unplug the network** | The TV says Offline; "Andy, where's the remote?" still works: SAM 3.1, Glimmer and the voice are on the computer beside the robot. "Pictures and voice stay in your home." |
| 1:46–2:04 | Quick cuts | "What am I holding?" (Glimmer says, locally) · "Draw me a lighthouse at dawn" (Muse Image fills the TV) · "Show me the weather radar on the TV" (Muse Spark's computer use, each click on the TV; about 11 s, so a labelled time cut) · "What do you remember?" (the map) |
| 2:04–2:16 | The reminder, two minutes later (a labelled time cut) | Andy finds the person, turns to them: "You asked me to remind you: drink some water." |
| 2:16–2:44 | The numbers and the models | The scorecard (simulated and physical, failures included), first word about a second after Andy understands, and every Meta model with where it runs: SAM 3.1, Muse Glimmer, Omnilingual ASR on our hardware; DINOv2 too; Muse Spark and Muse Image in the cloud (words, and screenshots of a web page asked for on the TV). |
| 2:44–3:00 | Robot close-up | What's next (our own robot design, as a silhouette only) and one line on why HeyAndy. |

**The cup game, if it scores well with real cups:** it replaces "Follow the mug" at 0:55 to 1:12 and becomes the X clip.
"Andy, let's play the cup game": the ball goes under a cup, a slow shuffle, "Let me replay that" (a labelled time cut over
the replay), Andy points, the cup is lifted, and the TV shows every cup's path. It shows SAM 3.1's Object Multiplex
doing what finding frame by frame can't: telling identical cups apart as they cross.

**"This is my mug," if the founder's two-mug test goes well:** it fits the uncut find (0:16 to 0:55) instead of "the
blue one": "Andy, this is my mug" (held up and turned), then with a second mug of another colour on the table, "Andy,
where's my mug?" The TV lists each mug's likeness ("58% like yours: not yours", "91%: yours"). It shows a Meta open model
(DINOv2) and the privacy story in one line: "I keep what it looks like as numbers, never a picture."

## Filming day, step by step

1. **Preflight** (a minute): `uv run python scripts/preflight.py --cloud` must end with "READY". Anything listed as
   FAIL says what to do; most often `systemctl --user restart heyandy-app` and run it again.
2. **The room:** staged. Nobody else in view, nothing personal (letters, photos, a phone or screen with anything
   private on it). The things for the takes in place: glasses (and a picture of glasses on the TV), the blue mug and a
   look-alike, keys, the remote; three opaque cups and a small bright ball if the cup game is in.
3. **The TV:** Chrome full screen (F11) on `http://127.0.0.1:8765`. If Andy was speaking Spanish, "Andy, speak English".
4. **Cameras:** the robot and the TV side by side in one shot, 1080p, normal speed. Start the TV recording just before
   each take: `uv run --with playwright python scripts/record_tv.py --seconds 200 --out film/take1.webm --room-is-staged`.
5. **Takes,** in the storyboard's order. Speak at a normal distance, start with "Andy", and wait for Andy to finish.
   Something goes wrong: "Andy, stop", then the next take; if Andy stops answering, restart it (step 1's command, 20 s)
   and run the preflight again.
6. **Between takes:** nothing to delete on this computer (Andy keeps no pictures or audio); `film/` is never committed.
   Keep every take that's used, uncut, for the "autonomous · uncut · 1× speed" badge.

**Recording the TV:** start `uv run --with playwright python scripts/record_tv.py --seconds 120 --out
film/tv-take1.webm --room-is-staged` just before each take, and line it up with the camera footage in the edit (Andy's first word is an
easy sync point). `film/` is never committed.

**Rules for filming:** no Meta logos; no music we don't own; subtitles burned in; no condition names and no health,
safety or loneliness claims; the people Andy is for are "people who live at home"; our own robot design is never
shown beyond a silhouette.

**For X (Most Viral):** the uncut take cut to 30 seconds, captions burned in, the same badge, posted after we submit.
