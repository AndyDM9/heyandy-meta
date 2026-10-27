"""One chat call to any OpenAI-compatible endpoint: the Meta Model API or a local llama.cpp/Ollama server."""
import re
import time

from .common import Reply
from .retry import with_retry

SYSTEM = ("Reasoning effort: low. You are Andy, a small tabletop robot in someone's home. If asked, you say you are "
          "a robot; don't introduce yourself otherwise (that's done for you). Answer in one to three short spoken "
          "sentences, no lists or markdown. You never give medical advice and never ask for money or passwords. "
          "In this conversation you can only talk: you cannot see, move, look for things, watch things, or set "
          "reminders, and you must never say you did or will. If asked to, tell the person to say it to you directly, "
          "for example: 'Andy, remind me at 3 pm to call Sam' or 'Andy, where are my keys?'")


def chat(client, model: str, prompt: str, source: str, max_tokens: int = 600, sleep=time.sleep,
         history=()) -> Reply:
    """history: the conversation so far, as (what the person said, what Andy said) pairs, oldest first."""
    start = time.monotonic()
    messages = [{"role": "system", "content": SYSTEM}]
    for said, answered in history:
        messages += [{"role": "user", "content": said}, {"role": "assistant", "content": answered}]
    out = with_retry(lambda: client.chat.completions.create(
        model=model, messages=messages + [{"role": "user", "content": prompt}], max_tokens=max_tokens,
    ), sleep=sleep)
    usage = getattr(out, "usage", None)
    return Reply(text=out.choices[0].message.content or "", source=source, latency_s=time.monotonic() - start,
                 tokens_in=getattr(usage, "prompt_tokens", 0) or 0, tokens_out=getattr(usage, "completion_tokens", 0) or 0)


SENTENCE_END = re.compile(r"[.!?]['\")]*\s+")  # a full stop followed by a space: "3.5" and "Dr.X" don't end one


def stream(client, model: str, prompt: str, history=(), max_tokens: int = 600, sleep=time.sleep):
    """The answer sentence by sentence, as it's written, so Andy can start speaking before it's finished."""
    messages = [{"role": "system", "content": SYSTEM}]
    for said, answered in history:
        messages += [{"role": "user", "content": said}, {"role": "assistant", "content": answered}]
    chunks = with_retry(lambda: client.chat.completions.create(
        model=model, messages=messages + [{"role": "user", "content": prompt}], max_tokens=max_tokens, stream=True,
    ), sleep=sleep)
    buf = ""
    for chunk in chunks:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue  # the model's thinking comes as reasoning_content, never spoken
        buf += delta
        while m := SENTENCE_END.search(buf):
            sentence, buf = buf[:m.end()].strip(), buf[m.end():]
            if sentence:
                yield sentence
    if buf.strip():
        yield buf.strip()


def sentences(text: str) -> list[str]:
    """A whole text, split the same way as a stream."""
    out, rest = [], text.strip() + " "
    while m := SENTENCE_END.search(rest):
        out.append(rest[:m.end()].strip())
        rest = rest[m.end():]
    return out + ([rest.strip()] if rest.strip() else [])
