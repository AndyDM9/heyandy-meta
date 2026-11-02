# Submitting (Wednesday November 4; the form closes at 9:00 PM ET, we aim for 3:00 PM)

What the judges get: the code (this repository, public), the 3-minute video, and the live product (the robot can't be
online, so its screen is: the Hugging Face Space). The form is at
https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit; re-read the live rules page before submitting.

**Before, on November 3**
- [ ] The founder's tests of what hasn't been tried on the robot yet (the founder's own test list: the cup game, my
      mug, going out, Spanish, "what's that?"), so the video and the text show only what works.
- [ ] `uv run python scripts/preflight.py --cloud` says READY (and again on the morning of November 4).
- [ ] The dress rehearsal says READY TO FILM, the room as it will be filmed (`docs/demo-script.md` step 2b).
- [ ] Film: the uncut find, follow the mug (or the cup game), several things at once, the network unplugged, a reminder
      (`docs/demo-script.md`). Recording the TV needs `uv run --with playwright playwright install ffmpeg` once.
- [ ] The physical scorecard (`evals/physical.py`), and its numbers in the README.
- [ ] The 30-second clip on X as soon as a take is good (Most Viral counts engagement through November 8): the uncut
      find or the cup game, captions burned in. Keep its link for the form (step 6).
- [x] Muse Spark live (since October 27, on our billing until the credits come; `docs/going-live.md`).
- [ ] Any last questions in Discord #questions (November 3 is the last full day for them).

**On November 4, in this order**
1. [ ] The video (the made cards: `uv run python scripts/film_cards.py --line "<the founder's words>"`; then the pieces and
       cards joined, sound evened out, length checked: `uv run python scripts/make_film.py cut film/cut.json --out film/andy.mp4`,
       `docs/demo-script.md` step 9): 3:00 or less; it opens with the founder's one line on what was pre-existing and what's new; uploaded
       where anyone can watch it signed out.
2. [ ] The README: the video at the top (uncomment the "Watch the 3-minute video" badge under the hero and put
       the link in it), the measured results, what was pre-existing, the limits; refresh the
       "What's new here" list up to date. The form text: `docs/submission.md`.
3. [ ] A last look through the history for anything private: no keys, no `docs/private/`, no home pictures
       (`git log -p | grep -E "MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}"` finds nothing). Never rewrite the history: its
       dates show the work was done during the event.
4. [ ] Make the repository public (GitHub, AndyDM9/heyandy-meta; its About already links the Space, with topics) and
       check a fresh clone passes its tests. First check
       GitHub Support has purged the old commits (the founder's ticket of November 1; the private status notes have the check).
5. [ ] Rebuild and upload the Space with the video's link for the story's end card
       (`uv run python scripts/build_static_space.py --video <the video's URL> --clip film/robot.mp4`: the story opens on
       about 10 s of the robot itself, `docs/demo-script.md`; then
       `hf upload heyandy-ai/andy dist/space-static . --repo-type space`), then make it public:
       `huggingface.co/spaces/heyandy-ai/andy` -> Settings -> visibility. Open it signed out: the
       the story (about 75 seconds) should play, end on the card, and "Watch the 3-minute video" should open the video;
       type "where are my keys?" in "Ask Andy": "Let me look", the views, then the find; tap 🎙 and say it (wav2vec 2.0
       downloads once, 95 MB): the same scene, and Chrome asks for the microphone only then; type "what won't you do?" (the
       promises card) and "I fell and I can't get up" (the note: 911 first, then the phone). Then "Try it on your own
       things": "No photo to hand? Use our cup", then "Our four cups" should end "There's your cup." (DINOv2 downloads
       once, 24 MB), and a photo of your own mug, then of the table, should work on a phone too; then "Sweep the room, live" on the
       phone (allow the camera): sweep slowly, the tone gets warmer, and the spotlight lands on your mug.
6. [ ] Submit: the representative (the founder), everyone who worked on it, the repository, the video, the X post's link, the Space,
       about 1,400 words on what it is and what's new (`docs/submission.md`: fill its [brackets], the video's link and
       the physical scorecard's "N of M"; if the scorecard wasn't run, delete that sentence: nothing goes in with a
       bracket), and the open-weights note (`docs/open-weights.md`).
7. [ ] Publish Andy Finder (0.2.0: "Ring it" works with nothing set up) to the Reachy Mini app store (Community prize; it links to this repository, so after step 4):
       `hf repo create andy-finder --repo-type space --space_sdk static` under the founder's account, then
       `hf upload <account>/andy-finder apps/andy_finder . --repo-type space`. The `reachy_mini_python_app` tag lists it.
8. [ ] After submitting: share the gallery page for the community vote.
