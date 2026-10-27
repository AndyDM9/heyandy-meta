"""One chat call to any OpenAI-compatible endpoint: the Meta Model API or a local llama.cpp/Ollama server."""
import time

from .common import Reply
from .retry import with_retry

SYSTEM = ("You are Andy, a small tabletop robot. You say you are a robot. Keep answers short and spoken. "
          "You never give medical advice and never ask for money or passwords.")


def chat(client, model: str, prompt: str, source: str, max_tokens: int = 300, sleep=time.sleep) -> Reply:
    start = time.monotonic()
    out = with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    ), sleep=sleep)
    usage = getattr(out, "usage", None)
    return Reply(text=out.choices[0].message.content or "", source=source, latency_s=time.monotonic() - start,
                 tokens_in=getattr(usage, "prompt_tokens", 0) or 0, tokens_out=getattr(usage, "completion_tokens", 0) or 0)
