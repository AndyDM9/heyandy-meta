import json
from types import SimpleNamespace

import pytest

from heyandy_meta.agent.loop import plan_search
from heyandy_meta.agent.tools import SearchTools
from heyandy_meta.budget import Budget, BudgetExceeded
from heyandy_meta.finder.search import Finder
from heyandy_meta.memory.places import Places
from heyandy_meta.robot.sim import Room, SimBody, SimSegmenter, Thing


class ScriptedSpark:
    """Plays Muse Spark: each turn is a list of (tool, args) calls, or a final string."""

    def __init__(self, *turns):
        self.turns, self.requests = list(turns), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        turn = self.turns.pop(0)
        usage = SimpleNamespace(prompt_tokens=800, completion_tokens=60)
        if isinstance(turn, str):
            msg = SimpleNamespace(content=turn, tool_calls=None)
        else:
            msg = SimpleNamespace(content="", tool_calls=[
                SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=n, arguments=a if isinstance(a, str) else json.dumps(a)))
                for i, (n, a) in enumerate(turn)])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def setup(*things, places=None):
    room = Room(list(things))
    body = SimBody(room)
    return SearchTools(Finder(body, SimSegmenter(room)), places), body


def test_a_good_plan_finds_and_points():
    tools, body = setup(Thing("reading glasses", -50.0, 20.0))
    spark = ScriptedSpark(
        [("look", {"object": "reading glasses", "views": ["far right", "right"]})],
        [("look_closer", {"object": "reading glasses", "place": "1"})],
        [("point", {"place": "1"})],
        "There they are, on the right.")
    plan = plan_search(spark, "I think I left my reading glasses by the TV on the right", tools)
    assert plan.reply == "There they are, on the right."
    assert [s[0] for s in plan.steps] == ["look", "look_closer", "point"]
    assert tools.pointed.yaw == pytest.approx(-50.0, abs=0.5)
    assert spark.requests[0]["tools"][0]["function"]["name"] == "recall"


def test_pointing_without_looking_closer_is_refused():
    tools, body = setup(Thing("keys", 20.0, 20.0))
    spark = ScriptedSpark(
        [("look", {"object": "keys", "views": ["left"]})],
        [("point", {"place": "1"})],
        "Sorry.")
    plan = plan_search(spark, "where are my keys", tools)
    assert plan.steps[1][2].startswith("refused")
    assert not [e for e in body.log if e[0] == "point"]


@pytest.mark.parametrize("name, args", [
    ("look", {"object": "keys", "views": ["up the chimney"]}),
    ("look", {"object": "keys; rm -rf /", "views": ["left"]}),
    ("look_closer", {"object": "keys", "place": "99"}),
    ("set_motor", {"joint": 3, "angle": 170}),
    ("look", "not json"),
])
def test_bad_arguments_are_refused_and_nothing_moves(name, args):
    tools, body = setup(Thing("keys", 20.0, 20.0))
    plan = plan_search(ScriptedSpark([(name, args)], "Sorry."), "find my keys", tools)
    assert plan.steps[0][2].startswith("refused")
    assert body.log == []


def test_recall_goes_to_the_remembered_place_first(tmp_path):
    places = Places(tmp_path / "p.json")
    places.watch("keys")
    places.saw("keys", -30.0, 18.0)
    tools, body = setup(Thing("keys", -30.0, 18.0), places=places)
    spark = ScriptedSpark(
        [("recall", {"object": "keys"})],
        [("look_closer", {"object": "keys", "place": "remembered"})],
        [("point", {"place": "remembered"})],
        "On the right, where you left them.")
    plan = plan_search(spark, "where are my keys", tools)
    assert sum(1 for e in body.log if e[0] == "capture") == 1  # one look, no sweep


def test_a_runaway_plan_is_stopped():
    tools, _ = setup()
    spark = ScriptedSpark(*[[("look", {"object": "keys", "views": ["left"]})]] * 20)
    plan = plan_search(spark, "find my keys", tools, max_calls=4)
    assert len(plan.steps) == 4 and plan.stopped
    assert "couldn't find" in plan.reply


def test_the_spend_cap_holds(monkeypatch):
    monkeypatch.delenv("HEYANDY_PAID_CALLS")
    with pytest.raises(BudgetExceeded):
        plan_search(ScriptedSpark("hi"), "find my keys", setup()[0])


def test_each_model_call_is_charged():
    budget = Budget()
    tools, _ = setup(Thing("keys", 20.0, 20.0))
    plan_search(ScriptedSpark([("look", {"object": "keys", "views": ["left"]})], "Found."), "keys?", tools, budget=budget)
    assert budget.spent() == pytest.approx(2 * (800 * 1.25 + 60 * 4.25) / 1e6)
