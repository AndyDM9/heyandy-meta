"""Muse Glimmer, answering at once: its reply started past its private reasoning.

Glimmer reasons in a message to itself (" to=self") before every answer, whatever its reasoning setting says; for a
one-word picture check or a short translation that's 2 to 3 s of the answer's time. llama-server renders the chat
template (/apply-template), and the reply is started at " to=user<|message|>", so the first token is the answer:
0.15 to 0.7 s (research.md, 23 and 24). Pictures go in as llama-server's multimodal data, in the order the template
placed their markers. Used only for short, fixed-format answers; planning and conversation keep their reasoning.
"""
import json
import urllib.error
import urllib.request

from .common import is_local

STOP = ["<|eot|>", "<|end|>", "<|start|>"]


class FastUnavailable(RuntimeError):
    pass


def answer(endpoint: str, messages: list[dict], max_tokens: int = 64, stop=(), timeout: float = 20.0) -> str:
    """The reply to ``messages`` (OpenAI-style; images as data URLs), with no reasoning first."""
    base = endpoint.rstrip("/").removesuffix("/v1")
    if not is_local(base):
        raise ValueError(f"Glimmer runs on this computer, not at {base}")
    images = [part["image_url"]["url"].split(",", 1)[1] for m in messages if isinstance(m.get("content"), list)
              for part in m["content"] if part.get("type") == "image_url"]

    def post(path: str, body: dict) -> dict:
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    try:
        prompt = post("/apply-template", {"messages": messages})["prompt"]
        prompt = prompt.replace("Reasoning strength: high.", "Reasoning strength: low.") + " to=user<|message|>"
        out = post("/completion", {"prompt": {"prompt_string": prompt, "multimodal_data": images} if images else prompt,
                                   "n_predict": max_tokens, "temperature": 0, "stop": STOP + list(stop)})
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        raise FastUnavailable(f"Glimmer at {base}: {e}") from e
    return (out.get("content") or "").strip()
