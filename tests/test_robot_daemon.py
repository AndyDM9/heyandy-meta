"""The robot's daemon, started through scripts/robot_daemon.py: its stream on this computer only, and the camera's rate
off unless asked, only rates the camera does."""
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


def test_the_daemon_always_starts_through_it():
    sh = (Path(__file__).resolve().parents[1] / "scripts" / "run-robot-daemon.sh").read_text()
    assert sh.rstrip().endswith('exec .venv/bin/python scripts/robot_daemon.py --headless "$@"')
    assert "reachy-mini-daemon --headless" not in sh  # Pollen's own entry point would offer the stream to the network


class _Sink:
    def __init__(self):
        self.props = {}

    def set_property(self, name, value):
        self.props[name] = value


def test_the_stream_is_offered_on_this_computer_only():
    """November 3: webrtcsink's signalling server listened on 0.0.0.0:8443, so the camera's and microphones' stream
    could be asked for from the home network. Each sink Pollen's media server makes is now told 127.0.0.1, once."""
    made = []

    class Server:
        def _configure_webrtc(self, pipeline):
            sink = _Sink()
            sink.set_property("run-signalling-server", True)
            made.append(sink)
            return sink

    class Module:
        GstMediaServer = Server

    robot_daemon.local_only(Module)
    robot_daemon.local_only(Module)  # twice is once
    sink = Server()._configure_webrtc("pipeline")
    assert sink.props == {"run-signalling-server": True, "signalling-server-host": "127.0.0.1"} and made == [sink]


def test_it_wont_start_wide_open_if_pollen_changes_the_step_it_wraps():
    class Module:
        class GstMediaServer:
            pass

    with pytest.raises(AttributeError):
        robot_daemon.local_only(Module)


def test_pollens_media_server_still_has_the_step_and_the_property_it_sets():
    media_server = pytest.importorskip("reachy_mini.media.media_server")
    assert callable(media_server.GstMediaServer._configure_webrtc)
    source = Path(media_server.__file__).read_text()
    assert 'set_property("run-signalling-server", True)' in source  # what makes the server it binds
