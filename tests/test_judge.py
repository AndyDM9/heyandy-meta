import io
from types import SimpleNamespace


import pytest
from openai import APIConnectionError
from PIL import Image

from heyandy_meta.agent.tools import SearchTools
from heyandy_meta.finder.judge import GlimmerJudge, NotLocal, crop
from heyandy_meta.models.common import is_local
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.body import Frame
from heyandy_meta.robot.sim import Room, SimBody, SimJudge, SimSegmenter, Thing


def jpeg(w=1920, h=1080) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (90, 120, 150)).save(out, "JPEG")
    return out.getvalue()


class Glimmer:
    """Plays the local llama-server: answers each request in turn, or fails to connect."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        a = self.answers.pop(0)
        if a is None:
            raise APIConnectionError(request=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=a))])


FRAME = Frame(jpeg(), 1920, 1080, 0.0, 15.0)
MUG = Mask("mug", (900, 500, 980, 580), 0.8, center=(940, 540))


@pytest.mark.parametrize("url, local", [
    ("http://127.0.0.1:8080/v1", True), ("http://localhost:8080/v1", True), ("http://192.168.1.20:8080/v1", True),
    ("http://[::1]:8080/v1", True), ("https://api.meta.ai/v1", False), ("http://8.8.8.8/v1", False)])
def test_only_local_addresses_count_as_local(url, local):
    assert is_local(url) is local


def test_pictures_are_never_sent_to_the_cloud():
    with pytest.raises(NotLocal):
        GlimmerJudge(endpoint="https://api.meta.ai/v1")


def test_crop_is_a_square_around_the_thing_with_its_surroundings():
    img = Image.open(io.BytesIO(crop(FRAME.image, MUG.box)))
    assert img.size == (256, 256)  # 80 px x 3 is under the 256 px floor
    big = Image.open(io.BytesIO(crop(FRAME.image, (0, 0, 400, 300))))
    assert big.size == (768, 768)  # 1200 px of context, at the corner, shrunk to the cap


def test_screen_check_says_picture_or_real():
    g = Glimmer("PICTURE", "REAL", "Hmm, hard to say")
    judge = GlimmerJudge(client=g)
    assert judge.real(FRAME, MUG) is False and "screen" in judge.why
    assert judge.real(FRAME, MUG) is True
    assert judge.real(FRAME, MUG) is True  # unsure counts as real: SAM 3.1 already saw it twice
    content = g.requests[0]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert g.requests[0]["model"] == "muse-glimmer-30B"


def test_when_glimmer_is_down_the_check_steps_aside():
    judge = GlimmerJudge(client=Glimmer(None))
    assert judge.real(FRAME, MUG) is True and judge.unavailable == 1


def test_pick_reads_the_number():
    two = [(FRAME, MUG), (FRAME, MUG)]
    assert GlimmerJudge(client=Glimmer("2")).pick(two, "the blue one") == 1
    assert GlimmerJudge(client=Glimmer("0")).pick(two, "the blue one") is None
    assert GlimmerJudge(client=Glimmer("Picture 7")).pick(two, "the blue one") is None
    assert GlimmerJudge(client=Glimmer(None)).pick(two, "the blue one") is None
    g = Glimmer("1")
    GlimmerJudge(client=g).pick(two, "the blue one")
    content = g.requests[0]["messages"][1]["content"]
    assert [c["type"] for c in content] == ["text", "image_url", "text", "image_url", "text"]


def test_a_picture_on_the_tv_is_not_pointed_at():
    room = Room([Thing("glasses", 50.0, 10.0, on_screen=True), Thing("glasses", -40.0, 20.0)])
    body = SimBody(room)
    f = Finder(body, SimSegmenter(room), check=SimJudge(room).real)
    found = f.find("glasses")
    assert found.yaw == pytest.approx(-40.0, abs=0.5)


def test_only_a_picture_means_nothing_found_and_says_why():
    room = Room([Thing("glasses", 50.0, 10.0, on_screen=True)])
    f = Finder(SimBody(room), SimSegmenter(room), check=SimJudge(room).real)
    assert f.find("glasses") is None
    assert "picture" in f.why


def mugs():
    room = Room([Thing("mug", 40.0, 15.0, looks="white, by the sink"),
                 Thing("mug", -20.0, 15.0, looks="blue, next to the laptop")])
    body = SimBody(room)
    tools = SearchTools(Finder(body, SimSegmenter(room)), judge=SimJudge(room))
    tools.call("look", {"object": "mug", "views": ["far left", "left", "right"]})
    return tools


def test_compare_picks_the_one_the_person_described():
    tools = mugs()
    out = tools.call("compare", {"object": "mug", "description": "the blue one next to the laptop",
                                 "places": list(tools.candidates)})
    chosen = next(p for p, s in tools.candidates.items() if s[0] < 0)
    assert out.startswith(f"Place {chosen} fits")
    assert list(tools.confirmed) == [chosen]  # the other mug can't be pointed at
    assert tools.call("point", {"place": chosen}).startswith("Pointing at the mug")


def test_compare_with_no_match_asks_the_person():
    tools = mugs()
    out = tools.call("compare", {"object": "mug", "description": "red", "places": list(tools.candidates)})
    assert "none looks like" in out and tools.confirmed == {}


@pytest.mark.parametrize("args", [
    {"object": "mug", "description": "blue; rm -rf /", "places": ["1", "2"]},
    {"object": "mug", "description": "blue", "places": ["1"]},
    {"object": "mug", "description": "blue", "places": ["1", "9"]}])
def test_compare_checks_its_arguments(args):
    assert mugs().call("compare", args).startswith("refused")


def test_compare_without_a_judge_says_so():
    tools = mugs()
    tools.judge = None
    assert "can't compare" in tools.call("compare", {"object": "mug", "description": "blue",
                                                    "places": list(tools.candidates)})


def test_describe_asks_glimmer_about_the_view_or_a_crop():
    g = Glimmer("A blue mug with a handle.", "A laptop and a mug.")
    judge = GlimmerJudge(client=g)
    assert judge.describe(FRAME, "in the person's hands", MUG.box) == "A blue mug with a handle."
    assert "in the person's hands" in g.requests[0]["messages"][1]["content"][0]["text"]
    assert judge.describe(FRAME, "on the table") == "A laptop and a mug."
    assert "never what to do with it" in g.requests[1]["messages"][1]["content"][0]["text"]


def test_a_colour_in_the_object_is_left_to_compare():
    room = Room([Thing("mug", 40.0, 15.0, looks="white, by the sink"),
                 Thing("mug", -20.0, 15.0, looks="blue, next to the laptop")])
    tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)), judge=SimJudge(room))
    out = tools.call("look", {"object": "Blue mug", "views": ["far left", "left", "right"]})
    assert out.startswith("Possible mug: place 1") and "use compare" in out  # every mug found, not none
    assert "already looked for the mug" in tools.call("look", {"object": "mug", "views": ["left"]})
    out = tools.call("compare", {"object": "blue mug", "description": "blue, next to the laptop",
                                 "places": list(tools.candidates)})
    assert "fits" in out and tools.pointed is not None and tools.pointed.yaw < 0


def test_where_it_is_and_place_names_as_models_write_them():
    room = Room([Thing("mug", 40.0, 15.0, looks="white, by the sink"),
                 Thing("mug", -20.0, 15.0, looks="blue, next to the laptop")])
    tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)), judge=SimJudge(room))
    assert tools.call("look", {"object": "mug next to the laptop", "views": ["far left", "left", "right"]}).startswith(
        "Possible mug: place 1")
    out = tools.call("compare", {"object": "mug", "description": "blue, next to the laptop",
                                 "places": ["place 1", "Place 2"]})
    assert "fits" in out and tools.pointed is not None


def test_when_the_person_said_which_one_a_guess_is_never_pointed_at():
    room = Room([Thing("phone", 40.0, 15.0, looks="red"), Thing("phone", -20.0, 15.0, looks="black")])
    tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)), judge=SimJudge(room))
    tools.call("look", {"object": "red phone", "views": ["far left", "left", "right"]})
    out = tools.call("look_closer", {"object": "red phone", "place": "1"})
    assert out.startswith("refused: there is more than one phone") and tools.pointed is None
    out = tools.call("compare", {"object": "phone", "description": "red", "places": ["1", "2"]})
    assert "fits" in out and tools.pointed.yaw > 0  # the red one, on the left


def test_one_found_that_isnt_the_one_described_isnt_pointed_at():
    room = Room([Thing("phone", -20.0, 15.0, looks="black")])
    tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)), judge=SimJudge(room))
    tools.call("look", {"object": "red phone", "views": ["far left", "left", "right"]})
    out = tools.call("look_closer", {"object": "phone", "place": "1"})
    assert "doesn't look like 'red'" in out and tools.pointed is None


def test_a_direction_in_the_object_isnt_taken_for_which_one():
    room = Room([Thing("glasses", 120.0, 20.0)])
    tools = SearchTools(Finder(SimBody(room), SimSegmenter(room)), judge=SimJudge(room))
    tools.call("look", {"object": "glasses behind you", "views": ["behind left"]})
    assert tools.described == ""
    assert tools.call("look_closer", {"object": "glasses", "place": "1"}).startswith("Confirmed")
