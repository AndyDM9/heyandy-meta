"""Where the desktop's sound would go if the monitor went away (scripts/desktop_audio.py), and its no-restart fix."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import desktop_audio as da  # noqa: E402

MONITOR = "alsa_output.pci-0000_01_00.1.hdmi-stereo-extra2"
ROBOT = "alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio_1-00.analog-stereo"


def sink(name, priority, nid=0):
    return {"id": nid, "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Audio/Sink", "node.name": name, "priority.session": priority}}}


def defaults(current, chosen=MONITOR):
    return {"type": "PipeWire:Interface:Metadata", "props": {"metadata.name": "default"},
            "metadata": [{"key": "default.audio.sink", "value": {"name": current}},
                         {"key": "default.configured.audio.sink", "value": {"name": chosen}}]}


def test_today_the_monitor_going_puts_the_sound_on_the_robots_speaker():
    d = [sink(MONITOR, 616), sink(ROBOT, 1009), defaults(MONITOR)]
    assert da.in_use(d) == (MONITOR, MONITOR)
    nxt = da.if_gone(da.sinks(d), MONITOR, [MONITOR, "xrdp-sink", "alsa_output.pci-0000_01_00.1.hdmi-stereo"])
    assert nxt == ROBOT and "jams" in da.describe(nxt)


def test_a_remembered_output_comes_first_then_the_highest_priority():
    outputs = {MONITOR: 616, ROBOT: 1009, "bluez_output.x": 900, da.SILENT: 2000}
    assert da.if_gone(outputs, MONITOR, [MONITOR, "bluez_output.x"]) == "bluez_output.x"
    assert da.if_gone(outputs, MONITOR, [MONITOR]) == da.SILENT
    assert da.if_gone({MONITOR: 616, "alsa_output.pci-0000_01_00.1.hdmi-stereo": 600}, MONITOR, []) is None  # its card's


def test_the_remembered_list_is_read_newest_first():
    state = ("[default-nodes]\ndefault.configured.audio.sink=A\ndefault.configured.audio.sink.0=A\n"
             "default.configured.audio.sink.1=B\ndefault.configured.audio.source=S\n")
    assert da.remembered(state) == ["A", "B"]


class Sound:
    """The sound system, faked: pw-dump's answer, and what pw-cli does to it (the priority is read from the node's
    own properties, as PipeWire does: the pactl way, first written, never set it)."""

    def __init__(self, misbehave=False):
        self.outputs, self.current, self.misbehave, self.calls = {MONITOR: 616, ROBOT: 1009}, MONITOR, misbehave, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] == "pw-dump":
            d = [sink(n, p, 104 if n == da.SILENT else 50) for n, p in self.outputs.items()] + [defaults(self.current)]
            return NS(returncode=0, stdout=json.dumps(d), stderr="")
        if cmd[:3] == ["pw-cli", "create-node", "adapter"]:
            import re

            props = cmd[3]
            assert f"node.name={da.SILENT}" in props and "media.class=Audio/Sink" in props and "object.linger=true" in props
            self.outputs[da.SILENT] = int(re.search(r"priority\.session=(\d+)", props).group(1))
            if self.misbehave:
                self.current = da.SILENT  # the sound moved: must be undone at once
            return NS(returncode=0, stdout="id: 104\n", stderr="")
        if cmd[:2] == ["pw-cli", "destroy"]:
            assert cmd[2] == "104"
            self.outputs.pop(da.SILENT, None)
            self.current = MONITOR
            return NS(returncode=0, stdout="", stderr="")
        raise AssertionError(cmd)


def test_apply_adds_the_silent_place_without_moving_the_sound(monkeypatch, tmp_path):
    monkeypatch.setattr(da, "STATE", tmp_path / "none")
    monkeypatch.setattr(da.time, "sleep", lambda s: None)
    s = Sound()
    assert da.apply(s) == 0
    assert s.current == MONITOR and s.outputs[da.SILENT] == 2000
    assert da.now(s)[1] == da.SILENT
    assert not any(c[0] == "systemctl" for c in s.calls)  # no restart of anything
    assert da.undo(s) == 0 and da.SILENT not in s.outputs


def test_if_the_sound_moves_it_is_taken_away_again(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(da, "STATE", tmp_path / "none")
    monkeypatch.setattr(da.time, "sleep", lambda s: None)
    s = Sound(misbehave=True)
    assert da.apply(s) == 1
    assert da.SILENT not in s.outputs and s.current == MONITOR
    assert "taken away again" in capsys.readouterr().out
