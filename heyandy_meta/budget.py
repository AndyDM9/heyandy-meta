"""A hard cap on Model API spend. Meta's own "spend limit" only sends an email; this one refuses the call.

Paid calls are off unless HEYANDY_PAID_CALLS=1. Each call's estimated cost is appended to a ledger, and a call
that would take the total past the cap is refused. Estimates use list prices (2026-10-27) and ignore cached-input
discounts, so they run high.
"""
import json
import os
import time
from pathlib import Path

PRICES = {  # dollars per 1M tokens (input, output), or per image
    "muse-spark-1.3": (1.25, 4.25),
    "muse-wonder-1.0": (4.00, 20.00),
}
SAM_PER_IMAGE = 2.50 / 1000
WEB_SEARCH = 2.50 / 1000  # Muse Spark's web_search tool, per search, on top of tokens


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, cap_usd: float = 140.0, ledger: str = "logs/spend.jsonl", env: str = "HEYANDY_PAID_CALLS"):
        self.cap, self.ledger, self.env = cap_usd, Path(ledger), env

    def spent(self) -> float:
        if not self.ledger.exists():
            return 0.0
        return sum(json.loads(line)["usd"] for line in self.ledger.read_text().splitlines() if line.strip())

    def check(self, worst_case_usd: float) -> None:
        """Before a call: refuse if paid calls are off or this call could pass the cap."""
        if os.environ.get(self.env) != "1":
            raise BudgetExceeded(f"paid calls are off; set {self.env}=1 once the hackathon credits show on Billing")
        if self.spent() + worst_case_usd > self.cap:
            raise BudgetExceeded(f"spend would pass the ${self.cap:.2f} cap (spent ${self.spent():.2f})")

    def record(self, model: str, usd: float) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "model": model, "usd": round(usd, 6)}) + "\n")


def chat_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICES[model]
    return (prompt_tokens * pin + completion_tokens * pout) / 1e6
