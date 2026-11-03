"""Where the desktop's sound would go if the monitor went away, and a silent place for it that needs no restart.

November 2 (docs/research.md section 77): the desktop's sound goes to the monitor's own speakers. When the monitor
was switched off or to another input, its output vanished and the sound system (WirePlumber 0.4) picked the next one:
none it remembered was there, so the highest priority, the robot's speaker (1009), which the robot's daemon holds at
16 kHz; it jammed, and Andy went deaf and mute. This reads, without changing anything, where the sound would go now;
--apply adds a silent output at priority 2000 to the running sound server, so the sound falls there instead: no
restart of the desktop's sound or of Andy, and it's gone at the next login (deploy/audio/ has the lasting version).
It checks that the sound in use now doesn't move, and that the next place is the silent one, or takes it away again.
Made with PipeWire's own pw-cli (a node that stays after it exits): made through pactl's module-null-sink, as first
written, its priority never reached PipeWire (it read 0, and the check took it away again: November 2, night).

    uv run python scripts/desktop_audio.py            # where it would go now (read-only)
    uv run python scripts/desktop_audio.py --apply    # the silent place, now; --undo takes it away
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROBOT = "Reachy_Mini_Audio"
SILENT = "heyandy_desktop_fallback"
PRIORITY = 2000  # above the robot's speaker (1009) and the monitor's (616)
STATE = Path.home() / ".local" / "state" / "wireplumber" / "default-nodes"


def sinks(dump: list) -> dict[str, int]:
    """Each output the sound server has now, with the priority it's chosen by."""
    out = {}
    for o in dump:
        p = (o.get("info") or {}).get("props") or {}
        if p.get("media.class") == "Audio/Sink" and p.get("node.name"):
            out[p["node.name"]] = int(p.get("priority.session") or 0)
    return out


def in_use(dump: list) -> tuple[str, str]:
    """(the output in use, the one chosen by hand): the sound system's own record of its defaults."""
    found = {}
    for o in dump:
        if o.get("type") == "PipeWire:Interface:Metadata" and (o.get("props") or {}).get("metadata.name") == "default":
            for m in o.get("metadata") or []:
                if m.get("key") in ("default.audio.sink", "default.configured.audio.sink"):
                    value = m.get("value")
                    value = json.loads(value) if isinstance(value, str) else value
                    found[m["key"]] = (value or {}).get("name", "")
    return found.get("default.audio.sink", ""), found.get("default.configured.audio.sink", "")


def remembered(state: str) -> list[str]:
    """The outputs chosen by hand before, newest first (WirePlumber tries these before any priority)."""
    names = []
    for line in state.splitlines():
        if line.startswith("default.configured.audio.sink"):
            names.append(line.split("=", 1)[1].strip())
    return list(dict.fromkeys(names))


def card(name: str) -> str:
    """The device an output belongs to (the monitor's HDMI outputs all go when it does)."""
    return name.rsplit(".", 1)[0] if name.startswith("alsa_output.") else name


def if_gone(outputs: dict[str, int], current: str, history: list[str]) -> str | None:
    """Where the sound would go if the output in use (and its device's others) went away: a remembered one that's
    still there, else the highest priority; None when nothing is left."""
    left = {n: p for n, p in outputs.items() if card(n) != card(current)}
    for name in history:
        if name in left:
            return name
    return max(left, key=lambda n: left[n]) if left else None


def describe(name: str | None) -> str:
    if name is None:
        return "nowhere (no other output): safe"
    if ROBOT in name:
        return f"the robot's speaker ({name}): it jams, Andy goes deaf and mute"
    if name == SILENT:
        return "the silent output: safe"
    return f"{name}: safe for the robot"


def dump(run=subprocess.run) -> list:
    out = run(["pw-dump"], capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        raise SystemExit(f"can't read the sound system (pw-dump): {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def now(run=subprocess.run) -> tuple[str, str | None, dict]:
    d = dump(run)
    outputs = sinks(d)
    current, chosen = in_use(d)
    history = remembered(STATE.read_text() if STATE.exists() else "") or ([chosen] if chosen else [])
    return current, if_gone(outputs, current, history), outputs


def node_id(run=subprocess.run) -> int | None:
    """The silent output's node, if it's there."""
    for o in dump(run):
        if ((o.get("info") or {}).get("props") or {}).get("node.name") == SILENT:
            return o.get("id")
    return None


PROPS = (f'{{ factory.name=support.null-audio-sink node.name={SILENT} node.description="Desktop fallback (silent)" '
         f"media.class=Audio/Sink audio.position=[ FL FR ] priority.session={PRIORITY} priority.driver={PRIORITY} "
         "object.linger=true }")


def apply(run=subprocess.run) -> int:
    before, nxt, _ = now(run)
    if nxt == SILENT:
        print(f"already there: the sound is on {before}; if that goes, {describe(nxt)}")
        return 0
    out = run(["pw-cli", "create-node", "adapter", PROPS], capture_output=True, text=True)
    if out.returncode != 0:
        print(f"the sound system refused it: {out.stderr.strip()[:200]}")
        return 1
    time.sleep(1.0)
    after, nxt, outputs = now(run)
    problems = []
    if after != before:
        problems.append(f"the sound in use moved from {before} to {after}")
    if outputs.get(SILENT) != PRIORITY:
        problems.append(f"the silent output's priority reads {outputs.get(SILENT)}, not {PRIORITY}")
    if nxt != SILENT:
        problems.append(f"if the monitor goes, the sound would still go to {nxt}")
    if problems:
        undo(run)
        print("taken away again: " + "; ".join(problems))
        return 1
    print(f"done, no restart: the sound stays on {after}; if that goes, {describe(nxt)}. Gone at the next login "
          f"(uv run python scripts/desktop_audio.py --undo to take it away now).")
    return 0


def undo(run=subprocess.run) -> int:
    nid = node_id(run)
    if nid is None:
        print("nothing to take away")
        return 0
    run(["pw-cli", "destroy", str(nid)], capture_output=True, text=True)
    print("the silent output is gone")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="add the silent output now (no restart; gone at next login)")
    ap.add_argument("--undo", action="store_true", help="take it away")
    args = ap.parse_args()
    if args.apply:
        sys.exit(apply())
    if args.undo:
        sys.exit(undo())
    current, nxt, outputs = now()
    print(f"the desktop's sound is on {current}")
    print(f"if that goes away (the monitor off or on another input), it goes to {describe(nxt)}")
    sys.exit(1 if nxt and ROBOT in nxt else 0)


if __name__ == "__main__":
    main()
