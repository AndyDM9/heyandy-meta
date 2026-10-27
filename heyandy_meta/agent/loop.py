"""Muse Spark plans a search with the tools, within a hard limit on calls and under the spend cap."""
import json
import time
from dataclasses import dataclass, field

from ..budget import Budget, chat_cost
from ..models.retry import with_retry
from .tools import VIEWS, SearchTools

SYSTEM = ("You are Andy, a small tabletop robot helping someone find a lost object in the room. Use the tools: "
          "recall first if the object might be watched, then look in the likeliest views (use what the person said), "
          "try other names for the object if needed (e.g. 'glasses case'), look_closer before you point, and point "
          "only at a confirmed place. If the person said which one (a colour, what it's next to) and you see more "
          "than one, use compare. Never guess. When done, reply with one short spoken sentence. Views: "
          + ", ".join(VIEWS) + ".")


@dataclass
class Plan:
    reply: str
    steps: list[tuple[str, dict, str]] = field(default_factory=list)  # tool, arguments, result
    stopped: str = ""  # why it ended early, if it did
    calls: int = 0  # model calls made


def plan_search(client, request: str, tools: SearchTools, model: str = "muse-spark-1.3",
                budget: Budget | None = None, max_calls: int = 12, max_tokens: int = 2000, sleep=time.sleep,
                paid: bool = True) -> Plan:
    """paid=False: a model on this computer (Muse Glimmer), which costs nothing and reasons briefly."""
    budget = budget or Budget()
    system = SYSTEM if paid else "Reasoning effort: low. " + SYSTEM
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    plan = Plan(reply="")
    while True:
        if paid:
            budget.check(chat_cost(model, sum(len(str(m.get("content") or "")) for m in messages) // 2 + 500,
                                   max_tokens))
        # Muse Spark reasons at length by default: "low" keeps a plan step to a few seconds, with room to answer.
        extra = {"reasoning_effort": "low"} if paid else {}
        out = with_retry(lambda: client.chat.completions.create(model=model, messages=messages, tools=tools.specs(),
                                                                max_tokens=max_tokens, **extra), sleep=sleep)
        usage = getattr(out, "usage", None)
        plan.calls += 1
        if paid:
            budget.record(model, chat_cost(model, getattr(usage, "prompt_tokens", 0) or 0,
                                           getattr(usage, "completion_tokens", 0) or 0))
        msg = out.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            plan.reply = msg.content or ""
            return plan
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": c.id, "type": "function",
                                         "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                        for c in calls]})
        for c in calls:
            if len(plan.steps) >= max_calls:
                plan.stopped = f"stopped after {max_calls} tool calls"
                plan.reply = _fallback(tools)
                return plan
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, "refused: arguments were not valid JSON"
            else:
                result = tools.call(c.function.name, args if isinstance(args, dict) else {})
            plan.steps.append((c.function.name, args, result))
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
        if tools.pointed:  # done: what Andy says is written from the tools' results, not by the model
            return plan


def _fallback(tools: SearchTools) -> str:
    if tools.pointed:
        return f"There's your {tools.pointed.label}."
    return "I'm sorry, I couldn't find it. Could you tell me where you last had it?"
