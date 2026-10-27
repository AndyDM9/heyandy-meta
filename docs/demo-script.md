# The 3-minute video (draft)

Judged on impact (30%), use of Meta's models (25%), technical depth (20%) and the demo (25%). One uncut take carries
the demo; the numbers carry the depth. Filmed on the Reachy Mini Lite in a staged room (no other people, nothing
personal in view). The TV page is screen-recorded at the same time.

| Time | On screen | Said, and what happens |
|---|---|---|
| 0:00–0:06 | Title card | **Required first line (FAQ):** what existed before (a Reachy Mini; an earlier object finder built before this event) and that everything shown was built this week on Meta's models. *(the founder's exact words)* |
| 0:06–0:16 | A person patting their pockets | The problem in one line: the same few things go missing every day, and a camera that streams your home to the cloud is a camera most people won't have. |
| 0:16–0:55 | **The uncut find**, robot and TV side by side, badge "autonomous · uncut · 1× speed" | "Andy, where are my glasses?" Andy turns to the voice, "Let me look", sweeps, **skips the glasses on the TV**, looks closer and points: "I see your glasses, to my right." The TV: the frame with SAM 3.1's outline, the plan, the timer, the models used. |
| 0:55–1:12 | **Follow the mug** (the X clip) | "Andy, follow the mug." The person slides it around the table; Andy's eyes stay on it, the base turning past the head's reach. "Stop." |
| 1:12–1:32 | **Several things at once** | "Andy, find the cup and remind me in two minutes to drink some water." The agent's steps appear on the TV; the robot points; "Your reminder is set." |
| 1:32–1:46 | **Unplug the network** | The TV says Offline; "Andy, where's the remote?" still works: SAM 3.1, Glimmer and the voice are on the computer beside the robot. "Pictures and voice stay in your home." |
| 1:46–2:04 | Quick cuts | "What am I holding?" (Glimmer says, locally) · "Draw me a lighthouse at dawn" (Muse Image fills the TV) · "What do you remember?" (the map) |
| 2:04–2:16 | The reminder, two minutes later (a labelled time cut) | Andy finds the person, turns to them: "You asked me to remind you: drink some water." |
| 2:16–2:44 | The numbers and the models | The scorecard (simulated and physical, failures included), first word about a second after Andy understands, and every Meta model with where it runs: SAM 3.1, Muse Glimmer, Omnilingual ASR on our hardware; Muse Spark and Muse Image in the cloud, words only. |
| 2:44–3:00 | Robot close-up | What's next (our own robot design, as a silhouette only) and one line on why HeyAndy. |

**Recording the TV:** start `uv run --with playwright python scripts/record_tv.py --seconds 120 --out
film/tv-take1.webm` just before each take, and line it up with the camera footage in the edit (Andy's first word is an
easy sync point). `film/` is never committed.

**Rules for filming:** no Meta logos; no music we don't own; subtitles burned in; no condition names and no health,
safety or loneliness claims; the people Andy is for are "people who live at home"; our own robot design is never
shown beyond a silhouette.

**For X (Most Viral):** the uncut take cut to 30 seconds, captions burned in, the same badge, posted after we submit.
