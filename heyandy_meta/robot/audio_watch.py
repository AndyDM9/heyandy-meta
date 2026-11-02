"""Andy watches its own ears and voice, and says on its TV when they stop.

November 2, 08:08: six seconds after the desktop's screen woke, the robot's audio device (the microphone array and the
speaker, "Reachy Mini Audio" on USB) stopped answering: the kernel refused its speaker interface ("usb_set_interface
failed (-71)", then thousands of "cannot submit urb") and every read of a voice's direction failed. Andy was deaf, and
very likely mute, for half an hour, and nothing on its TV or in its log said so (research.md section 73). Now, every
20 seconds, three plain signs, numbers only (no sound is kept or listened to here):

- the kernel's log since the last look: any new USB error from the audio device;
- the microphones: no sound at all from them for 10 seconds (they always hear something, even a quiet room);
- the direction of a voice: reads that fail (robot/reachy_mini.py counts them).

Any of them puts a lasting line on the TV with the fix, until a look finds none; "are you OK?" says it too.
"""
import subprocess
import threading
import time
from pathlib import Path

FAULTS = ("usb_set_interface failed", "cannot submit urb", "cannot get freq", "clock source")
FIX = "uv run python scripts/reset_robot_audio.py"


def port(devices: Path = Path("/sys/bus/usb/devices")) -> str | None:
    """The robot's audio device's USB port as the kernel names it ("1-5.2.1"), from its product name."""
    for d in sorted(devices.glob("*")):
        try:
            if (d / "product").read_text().strip() == "Reachy Mini Audio":
                return d.name
        except OSError:
            continue
    return None


def faults(kernel_log: str, where: str) -> int:
    """The kernel's complaints about the robot's audio device, in a stretch of its log."""
    return sum(1 for line in kernel_log.splitlines() if f"usb {where}:" in line and any(f in line for f in FAULTS))


class AudioWatch:
    def __init__(self, body, on_change=None, run=subprocess.run, clock=time.time, every_s: float = 20.0,
                 silent_s: float = 10.0, grace_s: float = 30.0, where: str | None = None):
        self.body, self.on_change, self.run, self.clock = body, on_change, run, clock
        self.every_s, self.silent_s = every_s, silent_s
        self.where = where if where is not None else port()
        self.started = clock()
        self.grace_until = self.started + grace_s  # the microphones' first sound comes a few seconds after a start
        self._since = self.started
        self._doa = getattr(body, "doa_failures", 0)
        self.trouble: str | None = None  # what's wrong, in words, while it is

    def _kernel(self, now: float) -> int:
        if not self.where:
            return 0
        try:
            log = self.run(["journalctl", "-k", "--since", f"@{int(self._since)}", "--no-pager", "-o", "cat"],
                           capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return 0
        self._since = now
        return faults(log, self.where)

    def check(self) -> str | None:
        """One look; returns the trouble in words, or None. Tells on_change when that changes."""
        now, problems = self.clock(), []
        usb = self._kernel(now)
        if usb:
            problems.append(f"{usb} USB errors")
        raw = getattr(self.body, "_raw", None)
        last = raw[-1][0] if raw else None
        if now > self.grace_until and (last is None or now - last > self.silent_s):
            problems.append(f"no sound from the microphones for {int(now - (last or self.started))} s")
        failed = getattr(self.body, "doa_failures", 0) - self._doa
        self._doa += failed
        if failed:
            problems.append(f"{failed} reads of a voice's direction failed")
        text = (f"My microphones and speaker stopped answering ({'; '.join(problems)}). Fix: {FIX}"
                if problems else None)
        if text != self.trouble:
            if text or self.trouble:
                print(text or "my microphones and speaker answer again", flush=True)
            self.trouble = text
            if self.on_change:
                self.on_change(text)
        return text

    def watch(self, stop: threading.Event) -> None:
        print(f"watching my microphones and speaker (USB {self.where or 'not found'}), every {self.every_s:.0f} s",
              flush=True)
        while not stop.wait(self.every_s):
            try:
                self.check()
            except Exception as e:  # noqa: BLE001 - the watch must never end Andy
                print(f"audio watch: {type(e).__name__}: {e}"[:200], flush=True)
