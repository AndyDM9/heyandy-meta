import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.companion.selfcheck import Part, Report, check, summary
from heyandy_meta.robot.sim import Thing
from heyandy_meta.screen.state import ScreenState
from tests.test_app import andy


class Service:
    def __init__(self, endpoint):
        self.endpoint = endpoint


def test_are_you_ok_checks_each_part_and_says_what_it_can_do(tmp_path):
    a, body, _ = andy(Thing("table", 0.0, 30.0), tmp_path=tmp_path)
    words = a.hear("Hey Andy, are you OK?")
    assert "I'm fine, thanks for asking! I can see, recognise things and move, all on this computer" in words
    rows = {r["name"]: r["status"] for r in a.screen.snapshot()["checked"]["rows"]}
    assert rows["my camera"] == "ok" and rows["turning my head"] == "ok" and rows["telling how far"] == "none"
    looks = [e for e in body.log if e[0] == "look"]
    assert len(looks) == 2 and looks[0][1] - looks[1][1] == pytest.approx(8.0)  # a small turn, and back


def test_a_service_not_answering_is_said_with_what_andy_can_still_do(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path)
    a.depth = Service("http://127.0.0.1:9")  # nothing listens on the discard port
    words = a.hear("check yourself")
    assert "Mostly fine, but 1 thing isn't working." in words
    assert "Telling how far (MapAnything): I can still find things and point, but not say how far." in words
    row = next(r for r in a.screen.snapshot()["checked"]["rows"] if r["name"] == "telling how far")
    assert row == {"name": "telling how far", "model": "MapAnything", "status": "down", "detail": "not answering"}


def test_a_head_that_doesnt_turn_is_down(tmp_path):
    a, body, _ = andy(tmp_path=tmp_path)
    body.look = lambda yaw, pitch, precise=True: None  # the motors don't answer: the head stays put
    report = check(a)
    moving = next(p for p in report.parts if p.key == "moving")
    assert moving.status == "down" and "turned 0 of 8 degrees" in moving.detail
    assert "Is the robot switched on?" in summary(report)


def test_the_summary_says_only_what_works_and_lists_at_most_two_problems():
    parts = [Part("camera", "my camera"), Part("seeing", "recognising things", "SAM 3.1"),
             Part("distance", "telling how far", "MapAnything", "none")]
    assert summary(Report(parts, 1.2)).startswith("I'm fine, thanks for asking! I can see and recognise things,")
    dark = [Part("camera", "my camera", status="warn", detail="it's dark in here"), Part("seeing", "recognising things")]
    assert "a bit dark in here" in summary(Report(dark, 1.0))
    broken = [Part(k, k, status="down", if_down=f"{k} is out.") for k in ("camera", "seeing", "moving")]
    said = summary(Report(broken, 1.0))
    assert said.startswith("Mostly fine, but 3 things aren't working.") and "The rest is on the screen." in said


def test_the_tv_lists_each_part():
    s = ScreenState()
    s.self_check([{"name": "my camera", "model": "", "status": "ok", "detail": "92 ms"}], 2.4)
    assert s.snapshot()["checked"] == {"rows": [{"name": "my camera", "model": "", "status": "ok", "detail": "92 ms"}],
                                       "seconds": 2.4}
    s.clear()
    assert s.snapshot()["checked"] is None


@pytest.mark.parametrize("text, kind", [("Hey Andy, are you OK?", "self_check"), ("run a self-check", "self_check"),
                                        ("is everything working?", "self_check"), ("¿estás bien?", "self_check"),
                                        ("I'm not OK", "chat"), ("is everything home?", "home_check")])
def test_asked_in_plain_words(text, kind):
    assert parse(text).kind == kind
