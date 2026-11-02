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


def test_a_service_start_is_given_to_journalctl_in_a_form_it_reads():
    """systemd's "Mon 2026-11-02 08:41:47 EST" is refused by journalctl; two checks read an empty log and passed."""
    from types import SimpleNamespace

    import pytest

    asked = []

    def run(cmd, **kw):
        asked.append(cmd)
        return SimpleNamespace(stdout="@1793626907\n")
    assert preflight.started("heyandy-robot", run=run) == "@1793626907" and "--timestamp=unix" in asked[0]
    with pytest.raises(RuntimeError, match="can't tell when"):
        preflight.started("heyandy-robot", run=lambda cmd, **kw: SimpleNamespace(stdout="Mon 2026-11-02 08:41:47 EST"))


def test_a_journal_that_cant_be_read_is_an_error_not_an_empty_log():
    from types import SimpleNamespace

    import pytest

    refused = lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="Failed to parse timestamp: Mon")  # noqa: E731
    with pytest.raises(RuntimeError, match="Failed to parse timestamp"):
        preflight.journal("-k", "--since", "Mon 2026-11-02 08:41:47 EST", run=refused)
    read = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="usb 1-5.2.1: cannot submit urb 0\n", stderr="")  # noqa: E731
    assert preflight.audio_usb_errors(preflight.journal("-k", run=read), "1-5.2.1") == 1


def test_this_computers_journalctl_reads_the_form_preflight_gives_it():
    import shutil
    import subprocess
    import time

    import pytest

    if not shutil.which("journalctl"):
        pytest.skip("no journalctl here")
    out = subprocess.run(["journalctl", "--since", f"@{int(time.time()) - 60}", "-n", "1", "--no-pager"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_no_answer_is_never_all_running_nor_all_capped():
    """Fail closed: a check that read nothing must not pass (November 2, three of preflight's could)."""
    import pytest

    with pytest.raises(RuntimeError, match="0 of 6"):
        preflight.services_down("")
    assert preflight.services_down("active\n" * 5 + "failed\n") == ["heyandy-app"]
    with pytest.raises(RuntimeError, match="0 cards"):
        preflight.power_too_high("")
    assert preflight.power_too_high("0, 300.00\n1, 300.00\n") == []
    assert preflight.power_too_high("0, 420.00\n1, 300.00\n") == ["GPU 0 at 420 W"]


def test_the_space_build_never_ships_a_library_file_it_didnt_check(tmp_path, monkeypatch):
    import hashlib

    import pytest

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_static_space as b

    monkeypatch.setattr(b, "CACHE", tmp_path)
    good = b"export const env = {};"
    monkeypatch.setitem(b.VENDOR, "x.js", ("pkg@1/x.js", hashlib.sha256(good).hexdigest()))
    assert b.vendored("x.js", fetch=lambda url: good) == good and (tmp_path / "x.js").read_bytes() == good
    assert b.vendored("x.js", fetch=lambda url: 1 / 0) == good  # from the cache now, no fetch
    (tmp_path / "x.js").write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="SHA-256 differs"):
        b.vendored("x.js", fetch=lambda url: b"something else")


def test_the_space_is_compared_with_the_build_file_by_file(tmp_path):
    """November 2: uploads add and replace, never remove, and Hugging Face's own template stylesheet from the Space's
    first commit was still there; scripts/verify_space.py says what differs."""
    import hashlib
    from types import SimpleNamespace

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from verify_space import compare

    for name, data in (("index.html", b"<html>"), ("vendor/rt.wasm", b"\0asm" * 9)):
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_bytes(data)
    local = {str(p.relative_to(tmp_path)): p for p in tmp_path.rglob("*") if p.is_file()}
    entry = lambda size, sha=None: SimpleNamespace(size=size, lfs=SimpleNamespace(sha256=sha) if sha else None)  # noqa: E731
    good = hashlib.sha256(b"\0asm" * 9).hexdigest()
    assert compare(local, {"index.html": entry(6), "vendor/rt.wasm": entry(36, good), ".gitattributes": entry(9)}) == \
        {"missing": [], "extra": [], "size": [], "sha256": []}
    assert compare(local, {"index.html": entry(5), "vendor/rt.wasm": entry(36, "0" * 64), "style.css": entry(3)}) == \
        {"missing": [], "extra": ["style.css"], "size": ["index.html"], "sha256": ["vendor/rt.wasm"]}


def test_andys_ports_must_listen_on_this_computer_only():
    import pytest

    from preflight import listening_wide

    ok = ("LISTEN 0 128 127.0.0.1:8765 0.0.0.0:*\nLISTEN 0 128 127.0.0.1:8080 0.0.0.0:*\n"
          "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\nLISTEN 0 128 [::1]:8000 [::]:*\n")
    assert listening_wide(ok) == []
    wide = listening_wide(ok + "LISTEN 0 128 0.0.0.0:8090 0.0.0.0:*\nLISTEN 0 128 [::]:8092 [::]:*\n"
                               "LISTEN 0 128 192.168.1.10:8096 0.0.0.0:*\n")
    assert [w.split(" on ")[0] for w in wide] == ["SAM 3.1 and the vision models", "the voice", "MapAnything"]
    with pytest.raises(RuntimeError, match="no listening port"):
        listening_wide("LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n")  # nothing of Andy's read: not a pass
