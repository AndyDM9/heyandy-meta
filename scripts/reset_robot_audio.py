"""The robot's microphones and speaker stopped answering: reset them, as unplugging and plugging the robot's USB would.

November 2, 08:08: the desktop's screen woke, and six seconds later the robot's audio device (a ReSpeaker array, "Reachy
Mini Audio" on USB) began refusing its interface changes (the kernel's log: "usb_set_interface failed (-71)", then
thousands of "cannot submit urb"). Every read of the voice's direction failed with an I/O error, and Andy's hearing
thread ended on the first one: Andy was deaf (it hears by loudness now when the direction can't be read, but a device in
that state may give no sound at all). Restarting the daemon and Andy didn't help; a USB reset of the audio device alone
did (the camera and motors are separate devices and aren't touched). preflight.py fails while the kernel log shows it.

    uv run python scripts/reset_robot_audio.py      # about 40 s: stops Andy and the daemon, resets, starts them again

November 4 (the morning of filming): the array went faint nine times, and this USB reset cured it for less each time,
because the board is powered from the USB cable and the chip's signal processing kept its state through a USB reset
and even the robot's power switch. What cured it was the chip's own REBOOT (XVF3800, through the daemon's audio
config API), so that comes first here, then the USB reset as before. Only the device's resets and the services; no
sound is recorded. The direction is read 20 times to check it answers.
"""
import json
import subprocess
import sys
import time
import urllib.request

VENDOR, PRODUCT = 0x38FB, 0x1001  # Pollen Robotics, Reachy Mini Audio
DAEMON = "http://127.0.0.1:8000"


def reboot_request(daemon: str = DAEMON) -> urllib.request.Request:
    """The array's own REBOOT, written through the robot's daemon: XMOS's XVF3800 "reboots the chip and resets all
    parameters to default". November 4: nine USB resets and two power cycles left the array faint (a voice reaching it
    at normal loudness but garbled, the room near-silent, the gain pinned), because the board is powered from the USB
    cable and its signal processing kept its state; this reset it, and Andy heard again within minutes."""
    body = json.dumps({"config": [{"name": "REBOOT", "values": [1]}], "verify": False}).encode()
    return urllib.request.Request(f"{daemon}/api/audio/config/apply", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")


def reboot_chip(daemon: str = DAEMON, opener=urllib.request.urlopen) -> bool:
    """Ask the daemon (while it runs) to reboot the array's chip. False if the daemon isn't up to pass it on."""
    try:
        with opener(reboot_request(daemon), timeout=10) as r:
            return bool(json.load(r).get("applied"))
    except Exception as e:  # noqa: BLE001 - no daemon, or a device that won't take it: the USB reset still follows
        print(f"the chip's own reboot couldn't be asked for ({type(e).__name__}): USB reset only", flush=True)
        return False


def direction_reads(n: int = 20) -> int:
    """How many of n reads of the voice's direction answer (the array's USB control)."""
    from reachy_mini.media.audio_doa import AudioDoA

    doa, ok = AudioDoA(), 0
    try:
        for _ in range(n):
            try:
                doa.get_DoA()
                ok += 1
            except OSError:
                pass
            time.sleep(0.05)
    finally:
        doa.close()
    return ok


def systemctl(*args: str) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


def main() -> None:
    import usb.core

    if reboot_chip():  # first, through the daemon while it runs: the chip's processing starts over
        print("the array's chip rebooted (its processing and parameters start over)", flush=True)
    systemctl("stop", "heyandy-app")
    systemctl("stop", "heyandy-robot")
    time.sleep(4)  # the chip comes back on USB in about a second; the daemon lets go of it
    dev = usb.core.find(idVendor=VENDOR, idProduct=PRODUCT)
    if dev is None:
        sys.exit("No Reachy Mini Audio on USB: is the robot plugged in and powered? Then: "
                 "systemctl --user start heyandy-robot heyandy-app")
    dev.reset()
    time.sleep(4)
    ok = direction_reads()
    print(f"the microphones' direction: {ok} of 20 reads answered", flush=True)
    systemctl("start", "heyandy-robot")
    time.sleep(15)  # the daemon finds the camera and sound card as it starts
    systemctl("start", "heyandy-app")
    if ok < 20:
        sys.exit("Still not answering: unplug the robot's USB cable, wait 5 s, plug it back, then run this again.")
    print("Reset. In about a minute: uv run python scripts/preflight.py --cloud")


if __name__ == "__main__":
    main()
