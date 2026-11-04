# Submitting (Wednesday November 4; the form closes at 9:00 PM ET, we aim for 3:00 PM)

What the judges get: the code (this repository, public), the 3-minute video, and the live product (the robot can't be
online, so its screen is: the Hugging Face Space). The form is at
https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit; re-read the live rules page before submitting.

**Before, on November 3**
- [ ] The founder's tests of what hasn't been tried on the robot yet (the founder's own test list: the cup game, my
      mug, going out, Spanish, "what's that?"), so the video and the text show only what works.
- [x] `uv run python scripts/preflight.py --cloud` says READY (November 3, 14:24; and again on the morning of November 4).
- [x] The dress rehearsal says READY TO FILM, the room as it will be filmed (`docs/demo-script.md` step 2b): November 3,
      every shot (`rehearsal-20261103-1155`, the keys `-only-1209`); again just before filming, in its light.
- [ ] Film: the uncut find, follow the mug (or the cup game), several things at once, the network unplugged, a reminder
      (`docs/demo-script.md`). Recording the TV needs `uv run --with playwright playwright install ffmpeg` once.
- [x] The physical scorecard (`evals/physical.py`), and its numbers in the README and the form text (November 1,
      evening: 13 of 15, `physical-fixed-20261101-2115`).
- [ ] The 30-second clip on X as soon as a take is good (Most Viral counts engagement through November 8): the uncut
      find or the cup game, captions burned in. Keep its link for the form (step 6).
- [x] Muse Spark live (since October 27, on our billing until the credits come; `docs/going-live.md`).
- [x] Any last questions in Discord #questions (November 3 is the last full day for them): read November 3, the
      organizers' answers on the video and the repository in `docs/rules.md`.

**On November 4, in this order** (first and last: `uv run python scripts/release_check.py --space`; it lists what's
left and must end READY TO SUBMIT before the form is sent in step 6, so the [brackets] are filled in step 2: the code pushed and its tests passed on GitHub, every figure, the
results page and the shared-link card current, no bracket left, the video badge up, no key in the history, every link
in the submission answering a visitor who isn't signed in, and the Space exactly the build)
1. [ ] The video (the made cards: `uv run python scripts/film_cards.py --line "<the founder's words>"`; then the pieces and
       cards joined, sound evened out, length checked: `uv run python scripts/make_film.py cut film/cut.json --out film/andy.mp4`,
       `docs/demo-script.md` step 9): 3:00 or less; it opens with the founder's one line on what was pre-existing and what's new; uploaded
       where anyone can watch it signed out.
       No take from the robot? The cards and the public demo's story, drawn as a film, make a 2:03 video on their own
       (`docs/demo-script.md`, "The story, as a film"): `film/andy-story.mp4`.
2. [ ] `uv run python scripts/claims.py`: every figure in the submission, the system card and the README's top says what
       its file says (a new run that changes one shows here; change the words, never the file). Fill the submission's
       [brackets] now (the video's link, the X post's), so the release check can say READY TO SUBMIT.
   [ ] The README's first picture: the real robot pointing, a short loop or a frame from the best take (the founder's
       camera, not the robot's), in place of the TV render (a judge-style review, November 3: in fifteen minutes a judge
       never saw the robot itself); the same clip is the Space's `--clip`.
   [ ] Andy Finder: the submission says it's in the app store from November 4 (`docs/submission.md`, "What's next");
       the founder approved publishing it that day (November 3), step 7. If it can't be, change that line first.
   [ ] The README: the video at the top (uncomment the "Watch the 3-minute video" badge under the hero and put
       the link in it), the measured results, what was pre-existing, the limits; refresh the
       "What's new here" list up to date. The form text: `docs/submission.md`.
3. [ ] A last look through the history for anything private: no keys, no `docs/private/`, no home pictures
       (the release check's "keys in the history" line, which looks for a key's value, not its name: the docs name
       MODEL_API_KEY often). Never rewrite the history: its
       dates show the work was done during the event.
4. [ ] Make the repository public (GitHub, AndyDM9/heyandy-meta; its About already links the Space, with topics) and
       check a fresh clone passes its tests. Then Settings -> General -> Social preview -> upload
       `docs/images/social-card.png` (by hand: GitHub has no API for it), so a posted link shows Andy's card. Then switch on private
       vulnerability reporting, where `SECURITY.md` sends reports (`gh api -X PUT repos/AndyDM9/heyandy-meta/private-vulnerability-reporting`;
       GitHub offers it only on a public repository), and switch off the empty wiki tab (`gh repo edit --enable-wiki=false`). GitHub Support
       has purged the old commits (the founder's ticket of November 1): checked November 3, none of the 182 replaced
       commits is served by its hash any more, nor their objects (the private status notes have the check).
5. [ ] Rebuild and upload the Space with the video's link for the story's end card
       (`uv run python scripts/build_static_space.py --video <the video's URL> --clip film/robot.mp4`: the front door and the story open on
       about 10 s of the robot itself, `docs/demo-script.md`; then
       `hf upload heyandy-ai/andy dist/space-static . --repo-type space`; then
       `uvx --from huggingface_hub python scripts/verify_space.py` must say none missing, extra or different), then make
       it public (if a scorecard changed since, `uv run python scripts/social_card.py` first: a test says so):
       `huggingface.co/spaces/heyandy-ai/andy` -> Settings -> visibility. Open it signed out: the
       the story (about 75 seconds) should play, end on the card, and "Watch the 3-minute video" should open the video;
       type "where are my keys?" in "Ask Andy": "Let me look", the views, then the find; tap 🎙 and say it (wav2vec 2.0
       downloads once, 95 MB): the same scene, and Chrome asks for the microphone only then; type "what won't you do?" (the
       promises card) and "I fell and I can't get up" (the note: 911 first, then the phone). Then "Try it on your own
       things": "No photo to hand? Use our cup", then "Our four cups" should end "There's your cup." (DINOv2 downloads
       once, 24 MB), and a photo of your own mug, then of the table, should work on a phone too; then "Sweep the room, live" on the
       phone (allow the camera): sweep slowly, the tone gets warmer, and the spotlight lands on your mug.
       And the card a shared link shows: paste the Space's link into a new post on X, and don't send it: Andy's card
       (`docs/images/social-card.png`), not Hugging Face's plain one; the same with the GitHub link once its preview is set.
6. [ ] Submit: the team's name (HeyAndy, Inc.), the representative (the founder), everyone who worked on it, the repository, the video, the X post's link, the Space,
       about 2,000 words on what it is and what's new (`docs/submission.md`; its header says what goes first if the form
       limits length): fill its [brackets], the video's link;
       nothing goes in with a bracket), and the open-weights note (`docs/open-weights.md`).
7. [ ] Publish Andy Finder (0.3.0: "Ring it" works with nothing set up; finds with the focus held, the true ray and its own aim check) to the Reachy Mini app store (Community prize; it links to this repository, so after step 4):
       `hf repo create andy-finder --repo-type space --space_sdk static` under the founder's account, then
       `hf upload <account>/andy-finder apps/andy_finder . --repo-type space --exclude "*.egg-info/*" --exclude "**/__pycache__/*"`
       (`hf upload` doesn't read `.gitignore`: without the exclusions, local build leftovers go up too). The `reachy_mini_python_app` tag lists it.
8. [ ] After submitting: share the gallery page for the community vote.
