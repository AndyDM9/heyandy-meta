# Submitting (Wednesday November 4; the form closes at 9:00 PM ET, we aim for 3:00 PM)

What the judges get: the code (this repository, public), the 3-minute video, and the live product (the robot can't be
online, so its screen is: the Hugging Face Space). The form is at
https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit; re-read the live rules page before submitting.

**Before, on November 3**
- [ ] Film: the uncut find, the look-alikes, the network unplugged, a reminder (`docs/demo-script.md`).
- [ ] The physical scorecard (`evals/physical.py`), and its numbers in the README.
- [ ] Muse Spark live (`docs/going-live.md`), if the credits have come.
- [ ] Any last questions in Discord #questions (November 3 is the last full day for them).

**On November 4, in this order**
1. [ ] The video: 3:00 or less; it opens with the founder's one line on what was pre-existing and what's new; uploaded
       where anyone can watch it signed out.
2. [ ] The README: the video at the top, the measured results, what was pre-existing, the limits; refresh the
       "What's new here" list (it dates from October 27 morning). The form text: `docs/submission.md`.
3. [ ] A last look through the history for anything private: no keys, no `docs/private/`, no home pictures
       (`git log -p | grep -E "MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}"` finds nothing). Never rewrite the history: its
       dates show the work was done during the event.
4. [ ] Make the repository public (GitHub, AndyDM9/heyandy-meta) and check a fresh clone passes its tests.
5. [ ] Make the Space public: `huggingface.co/spaces/heyandy-ai/andy` -> Settings -> visibility. Open it signed out.
6. [ ] Submit: the representative (the founder), everyone who worked on it, the repository, the video, the Space,
       about 1,000 words on what it is and what's new, and the open-weights note (`docs/open-weights.md`).
7. [ ] After submitting: the 30-second clip on X (Most Viral, judged to November 8), its link added to the submission;
       share the gallery page for the community vote.
