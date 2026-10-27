# Switching on Muse Spark (when the credits show on Billing)

Until then Andy runs entirely on this computer. These steps are the founder's to do: the key is never shown to anyone
else or put in the repository.

1. **Check Billing** on the Meta Model API: the $150 hackathon credits are there, and the spend limit is $150.
2. **Create an API key** for the HeyAndy, Inc. team. Use the Standard tier models only; never a `-contributor` model
   (Meta may train on their inputs; the code refuses them anyway).
3. **Save it where only you can read it,** outside the repository:
   ```bash
   mkdir -p ~/.config/heyandy-meta && touch ~/.config/heyandy-meta/env && chmod 600 ~/.config/heyandy-meta/env
   nano ~/.config/heyandy-meta/env   # two lines: MODEL_API_KEY=...   and   HEYANDY_PAID_CALLS=1
   ```
4. **The smoke test** (a few cents, capped):
   ```bash
   set -a; . ~/.config/heyandy-meta/env; set +a
   uv run python scripts/smoke_model_api.py
   ```
   It checks Muse Spark chat, planning a search with the tools, web answers with sources, and SAM 3.1 through the API
   on a drawn picture. The summary goes to `evals/results/smoke-model-api-*.json`.
5. **Restart Andy:** `systemctl --user restart heyandy-app`. The TV's first line says "Muse Spark: on".

What changes: a request with a hint ("by the TV") is planned by Muse Spark when online (Glimmer when not); questions
about the world ("what's the weather tomorrow?") are answered with web search and their sources on the TV; harder
questions in conversation go to Muse Spark. Muse Spark only ever gets words. The spend is logged in `logs/spend.jsonl`
and refused past $140.

**Filming in a staged room only:** `--staged-scene` makes the finder send camera frames to SAM 3.1 through the API, and
the TV says so. Never in a lived-in room: Meta can't turn off data retention for hackathon credits.
