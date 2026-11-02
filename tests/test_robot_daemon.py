"""The camera-rate launcher: off unless asked, and only rates the camera does."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import robot_daemon  # noqa: E402


def test_unset_leaves_pollens_rate():
    assert robot_daemon.cap({}) is None and robot_daemon.cap({"HEYANDY_CAMERA_FPS": " "}) is None


def test_a_rate_the_camera_does_is_taken():
    assert robot_daemon.cap({"HEYANDY_CAMERA_FPS": "20"}) == 20


@pytest.mark.parametrize("raw", ["0", "61", "120"])
def test_a_rate_the_camera_cant_do_stops_it(raw):
    with pytest.raises(SystemExit):
        robot_daemon.cap({"HEYANDY_CAMERA_FPS": raw})


def test_the_constant_it_sets_is_still_pollens():
    """If Pollen renames IPC_FPS, setting it would silently do nothing: fail here instead."""
    media_server = pytest.importorskip("reachy_mini.media.media_server")
    assert isinstance(media_server.IPC_FPS, int)


def test_the_daemon_script_uses_it_only_when_asked():
    sh = (Path(__file__).resolve().parents[1] / "scripts" / "run-robot-daemon.sh").read_text()
    assert 'if [ -n "${HEYANDY_CAMERA_FPS:-}" ]' in sh and sh.rstrip().endswith('exec .venv/bin/reachy-mini-daemon --headless "$@"')
