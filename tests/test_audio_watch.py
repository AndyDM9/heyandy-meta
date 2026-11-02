"""Andy watches its own ears and voice (robot/audio_watch.py): November 2 they stopped for half an hour, unsaid."""
from types import SimpleNamespace

from heyandy_meta.robot.audio_watch import FIX, AudioWatch, faults

BROKEN = "usb 1-5.2.1: 1:0: usb_set_interface failed (-71)\nusb 1-5.2.1: cannot submit urb 0, error -2: endpoint not enabled\n"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def kernel(*logs):
    """journalctl -k, answering each look with the next stretch of log; the asked --since kept."""
    asked, logs = [], list(logs)

    def run(cmd, **kw):
        asked.append(cmd[cmd.index("--since") + 1])
        return SimpleNamespace(stdout=logs.pop(0) if logs else "")
    return run, asked


def ears(heard_at=None, doa_failures=0):
    return SimpleNamespace(_raw=[(heard_at, 0, None)] if heard_at is not None else [], doa_failures=doa_failures)


def test_a_healthy_robot_says_nothing():
    clock, (run, asked) = Clock(), kernel("")
    body, shown = ears(), []
    watch = AudioWatch(body, shown.append, run=run, clock=clock, where="1-5.2.1")
    clock.t += 20
    body._raw.append((clock.t - 0.1, 0, None))
    assert watch.check() is None and shown == [] and asked == ["@1000"]


def test_usb_errors_put_a_lasting_line_with_the_fix_on_the_tv_until_they_stop():
    clock, (run, asked) = Clock(), kernel(BROKEN * 100, BROKEN, "")
    body, shown = ears(), []
    watch = AudioWatch(body, shown.append, run=run, clock=clock, where="1-5.2.1")
    for _ in range(3):
        clock.t += 20
        body._raw.append((clock.t - 0.1, 0, None))
        watch.check()
    assert shown[0] == f"My microphones and speaker stopped answering (200 USB errors). Fix: {FIX}"
    assert shown[1].startswith("My microphones and speaker stopped answering (2 USB errors)") and shown[2] is None
    assert asked == ["@1000", "@1020", "@1040"]  # each look reads only what's new


def test_silent_microphones_after_the_start_and_failed_direction_reads_are_trouble_too():
    clock, (run, _) = Clock(), kernel()
    body, shown = ears(), []
    watch = AudioWatch(body, shown.append, run=run, clock=clock, where="1-5.2.1")
    clock.t += 20
    assert watch.check() is None  # nothing heard yet, but just started: the first sound takes a few seconds
    clock.t += 20
    assert "no sound from the microphones for 40 s" in watch.check()
    body._raw.append((clock.t, 0, None))
    body.doa_failures = 7
    clock.t += 5
    assert watch.check() == f"My microphones and speaker stopped answering (7 reads of a voice's direction failed). Fix: {FIX}"
    clock.t += 5
    assert watch.check() is None and shown[-1] is None


def test_no_audio_device_or_no_journal_is_not_trouble_by_itself():
    def broken(cmd, **kw):
        raise OSError("no journalctl")
    clock = Clock()
    watch = AudioWatch(ears(clock.t), run=broken, clock=clock, where="1-5.2.1")
    clock.t += 5
    assert watch.check() is None
    assert AudioWatch(ears(clock.t), run=broken, clock=clock, where="").check() is None


def test_only_the_audio_devices_own_lines_count():
    assert faults(BROKEN + "usb 1-5.2.4: cannot submit urb 0\nusb 1-5.2.1: reset high-speed USB device\n", "1-5.2.1") == 2


def test_the_tv_shows_the_trouble_and_are_you_ok_says_it():
    from heyandy_meta.screen.state import ScreenState

    state = ScreenState()
    state.trouble("My microphones and speaker stopped answering (3 USB errors). Fix: " + FIX)
    assert state.snapshot()["trouble"].endswith(FIX)
    state.trouble(None)
    assert state.snapshot()["trouble"] == ""
