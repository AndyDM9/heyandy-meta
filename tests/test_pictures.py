import base64
import json
import urllib.request
from types import SimpleNamespace as NS

import pytest

from heyandy_meta.companion import pictures
from heyandy_meta.companion.intents import parse
from heyandy_meta.screen.server import serve
from tests.test_app import andy

WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 fake"


class MuseImage:
    def __init__(self):
        self.requests = []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.requests.append(kw)
        return NS(id=f"resp_{len(self.requests)}", output=[NS(type="reasoning"), NS(type="message", content=[]),
                                                             NS(type="image_generation_call", result=base64.b64encode(WEBP).decode())])


@pytest.fixture(autouse=True)
def pictures_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(pictures, "FOLDER", tmp_path / "Pictures" / "Andy")
    return tmp_path / "Pictures" / "Andy"


@pytest.mark.parametrize("said, what", [
    ("Andy, draw me a picture of a cat asleep in a sunny garden", "a cat asleep in a sunny garden"),
    ("paint a lighthouse at dawn", "lighthouse at dawn"),
    ("can you make me a picture of my grandson's dog in a party hat?", "my grandson's dog in a party hat")])
def test_draw_requests(said, what):
    i = parse(said)
    assert (i.kind, i.text) == ("draw", what)


def test_make_a_picture_is_not_a_reminder_or_a_find():
    assert parse("where is my drawing pad").kind == "find"


def test_a_picture_is_made_shown_saved_and_refined(tmp_path, pictures_folder):
    image = MuseImage()
    a, _, _ = andy(tmp_path=tmp_path, spark=image)
    reply = a.hear("Andy, draw me a picture of a cat asleep in a sunny garden")
    assert "Here's your picture" in reply and image.requests[0]["model"] == "muse-image-1.0"
    assert image.requests[0]["input"] == "a cat asleep in a sunny garden"
    saved = list(pictures_folder.glob("andy-*.webp"))
    assert len(saved) == 1 and saved[0].read_bytes() == WEBP
    snap = a.screen.snapshot()
    assert snap["drawing"]["prompt"] == "a cat asleep in a sunny garden" and snap["picture"] is None
    assert {m["name"]: m["where"] for m in snap["models"]}["Muse Image"] == "cloud"

    assert "I've changed it" in a.hear("make it a golden sunset")
    assert image.requests[1]["previous_response_id"] == "resp_1" and image.requests[1]["input"] == "make it a golden sunset"
    assert a.screen.snapshot()["drawing"]["v"] == 2


def test_no_pictures_offline(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path, spark=MuseImage(), online=False)
    assert "only make pictures when I'm connected" in a.hear("draw me a cat")


def test_the_tv_serves_the_picture_itself(tmp_path):
    a, _, _ = andy(tmp_path=tmp_path, spark=MuseImage())
    a.hear("draw me a cat")
    srv = serve(a.screen, port=0)
    try:
        url = f"http://127.0.0.1:{srv.server_port}"
        assert urllib.request.urlopen(url + "/drawing.webp").read() == WEBP
        assert json.load(urllib.request.urlopen(url + "/state.json"))["drawing"]["v"] == 1
    finally:
        srv.shutdown()
