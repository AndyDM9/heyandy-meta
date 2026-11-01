# Muse Spark and Muse Image: the cloud part

Muse Spark has been live since October 27, on our own billing until the hackathon credits come. These steps are the
founder's: the key is never shown to anyone else or put in the repository.

1. **Billing** on the Meta Model API: a spend limit set. The code also stops at $140 (`heyandy_meta/budget.py`).
2. **An API key** for the HeyAndy, Inc. team. Standard tier only; never a `-contributor` model (Meta may train on their
   inputs; the code refuses them anyway).
3. **Saved where only you can read it,** outside the repository:
   ```bash
   mkdir -p ~/.config/heyandy-meta && touch ~/.config/heyandy-meta/env && chmod 600 ~/.config/heyandy-meta/env
   nano ~/.config/heyandy-meta/env   # MODEL_API_KEY=...   HEYANDY_PAID_CALLS=1   HEYANDY_HOME=Your town, State
   ```
   `HEYANDY_HOME` is the town only (for the weather and anything local), never a street or ZIP.
4. **The smoke test** (a few cents, capped): `set -a; . ~/.config/heyandy-meta/env; set +a; uv run python
   scripts/smoke_model_api.py`. The summary goes to `evals/results/smoke-model-api-*.json`.
5. **Restart Andy:** `systemctl --user restart heyandy-app` (the service reads the env file). Without a connection the
   TV shows "Offline: working on this computer" and Andy carries on.

What the cloud does: plans hinted searches and requests with several parts (Glimmer does when offline); web answers
with their sources; the morning briefing's and going out's weather; harder conversation (never a health question:
those get Andy's own words, and no model sees them); Muse Spark's computer use for
"show me ... on the TV" (needs the `browse` extra and `playwright install --only-shell chromium`); Muse Image for
pictures and the map of your things. The cloud gets words, and, for the web on the TV, screenshots of web pages only.
Every turn the TV's privacy receipt shows exactly what went. Spend is logged in `logs/spend.jsonl` and refused past $140.

**Filming in a staged room only:** `--staged-scene` makes the finder send camera frames to SAM 3.1 through the API, and
the TV says so. Never in a lived-in room: Meta can't turn off data retention for hackathon credits.
