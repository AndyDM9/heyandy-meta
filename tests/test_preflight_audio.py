"""Preflight reads the kernel's log for the robot's audio device: November 2 it stopped answering and Andy went deaf."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import preflight  # noqa: E402

LOG = """usb 1-5.2.1: 1:0: usb_set_interface failed (-71)
usb 1-5.2.1: cannot submit urb 0, error -2: endpoint not enabled
usb 1-5.2.4: cannot submit urb 0, error -2: endpoint not enabled
usb 1-5.2.1: uac_clock_source_is_valid(): cannot get clock validity for id 1
usb 1-5.2.1: reset high-speed USB device number 12 using xhci_hcd
xhci_hcd 0000:00:14.0: xHCI Host Controller"""


def test_the_robot_audio_devices_complaints_are_counted_and_no_others():
    assert preflight.audio_usb_errors(LOG, "1-5.2.1") == 2  # the reset itself and another device's lines aren't
    assert preflight.audio_usb_errors(LOG.replace("cannot get clock validity", "cannot get freq"), "1-5.2.1") == 3
    assert preflight.audio_usb_errors("usb 1-5.2.1: new high-speed USB device number 12", "1-5.2.1") == 0


def test_the_audio_device_is_found_by_its_product_name(tmp_path):
    for name, product in (("1-5.2.4", "Reachy Mini Camera"), ("1-5.2.1", "Reachy Mini Audio"), ("1-5.2:1.0", None)):
        (tmp_path / name).mkdir()
        if product:
            (tmp_path / name / "product").write_text(product + "\n")
    assert preflight.audio_port(tmp_path) == "1-5.2.1"
    (tmp_path / "1-5.2.1" / "product").write_text("Something else\n")
    assert preflight.audio_port(tmp_path) is None
