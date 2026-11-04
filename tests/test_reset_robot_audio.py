"""The robot's audio reset: the array's chip rebooted through the daemon first (November 4), then the USB reset."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reset_robot_audio as r  # noqa: E402


def test_the_reboot_is_the_daemons_audio_config_apply_with_the_xvf_reboot_command():
    req = r.reboot_request("http://127.0.0.1:8000")
    assert req.full_url == "http://127.0.0.1:8000/api/audio/config/apply" and req.get_method() == "POST"
    assert json.loads(req.data) == {"config": [{"name": "REBOOT", "values": [1]}], "verify": False}
    assert req.get_header("Content-type") == "application/json"


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_reboot_chip_says_whether_the_daemon_applied_it():
    asked = []

    def opener(req, timeout):
        asked.append(req.full_url)
        return Answer(b'{"applied": true}')

    assert r.reboot_chip("http://d", opener=opener) is True and asked == ["http://d/api/audio/config/apply"]
    assert r.reboot_chip("http://d", opener=lambda req, timeout: Answer(b'{"applied": false}')) is False


def test_without_a_daemon_the_reboot_is_skipped_not_fatal(capsys):
    def down(req, timeout):
        raise ConnectionRefusedError("no daemon")

    assert r.reboot_chip("http://d", opener=down) is False
    assert "USB reset only" in capsys.readouterr().out
