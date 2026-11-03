"""Andy watches its own ears and voice, and says on its TV when they stop.

November 2, 08:08: six seconds after the desktop's screen woke, the robot's audio device (the microphone array and the
speaker, "Reachy Mini Audio" on USB) stopped answering: the kernel refused its speaker interface ("usb_set_interface
failed (-71)", then thousands of "cannot submit urb") and every read of a voice's direction failed. Andy was deaf, and
very likely mute, for half an hour, and nothing on its TV or in its log said so (research.md section 73). Now, every
20 seconds, three plain signs, numbers only (no sound is kept or listened to here):

- the kernel's log since the last look: any new USB error from the audio device;
- the microphones: no sound at all from them for 10 seconds (they always hear something, even a quiet room);
- the direction of a voice: reads that fail (robot/reachy_mini.py counts them);

And `faint`, for scripts/preflight.py: what Andy hears too faint to make out (November 3: from about 10:36 the array's
sound fell tenfold and Omnilingual ASR wrote nonsense from it, so Andy never heard its name). Not on the TV: replayed
over the day, it also flagged a quiet room's faint noises while Andy was answering normally.

Any of them puts a lasting line on the TV with the fix, until a look finds none; "are you OK?" says it too.
"""
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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


def faint(rooms, gain: float | None, answered: int = 0, up_s: float = 0.0, least: int = 8,
          loudness=None) -> tuple[bool, str]:
    """Has the microphone array gone too faint to hear by, as on November 3? rooms: the room's level beside each sound
    Andy let go lately; loudness: each of those sounds' own loudness (numbers only); gain: the array's own automatic
    gain now (PP_AGCGAIN, from its daemon). The fault's signature: even the loudest sounds faint (the 90th percentile
    under 0.02: at 10:41 nothing came above 0.009, while voices arrive at 0.04 to 0.14), a near-silent room level
    (under 0.003) with the gain barely on (under 2), no turn answered lately (one answered: it hears its name), and the
    daemon up ten minutes (the gain starts low after a reset and climbs). Without the loudest sounds' test, loud talk
    near the robot (which turns the gain down) and then a quiet room looked the same (14:50, a false alarm). Fewer than
    `least` sounds: too few to tell."""
    rooms, loud = sorted(rooms), sorted(loudness or [])
    if answered:
        return False, f"{answered} turns answered lately: it hears its name"
    if len(rooms) < least or len(loud) < least:
        return False, f"{min(len(rooms), len(loud))} sounds lately: too few to tell"
    room, loudest = rooms[len(rooms) // 2], loud[int(len(loud) * 0.9)]
    said = (f"room level {room:.3f} (median of {len(rooms)}), the loudest sounds {loudest:.3f}, the array's gain "
            f"{'unread' if gain is None else f'{gain:.2f}'}")
    return (gain is not None and gain < 2.0 and room < 0.003 and loudest < 0.02 and up_s >= 600), said


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
        self.unread = 0  # looks at the kernel's log that couldn't be read

    def _kernel(self, now: float) -> int:
        if not self.where:
            return 0
        try:
            out = self.run(["journalctl", "-k", "--since", f"@{int(self._since)}", "--no-pager", "-o", "cat"],
                           capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            out = SimpleNamespace(returncode=1, stdout="", stderr=str(e))
        if getattr(out, "returncode", 0) != 0:  # can't read it: said once, never taken for "no errors" in silence
            if not self.unread:
                print(f"can't read the kernel's log to watch my microphones and speaker: "
                      f"{(out.stderr or '').strip()[:100]}", flush=True)
            self.unread += 1
            return 0
        self._since = now
        return faults(out.stdout, self.where)

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
