import pytest

from heyandy_meta.companion.intents import parse
from heyandy_meta.finder.names import also, snap
from heyandy_meta.finder.search import Finder
from heyandy_meta.models.common import Mask
from heyandy_meta.robot.sim import Room, SimBody, Thing


@pytest.mark.parametrize("heard, meant", [("cop", "cup"), ("the cop", "the cup"), ("kees", "keys"), ("cup", "cup"),
                                          ("blue mug", "blue mug"), ("zebra", "zebra"), ("wallets", "wallet")])
def test_a_misheard_thing_snaps_to_the_nearest_known_one(heard, meant):
    assert snap(heard) == meant


def test_where_is_the_cop_means_the_cup():
    assert parse("andy where is the cop").thing == "cup"


def test_close_names_are_asked_for_in_one_request():
    asked = []

    class Many:
        def find_many(self, frame, names):
            asked.append(names)
            return {n: [Mask(n, (930, 520, 976, 564), 0.8, center=(953.0, 542.0))] if n == "mug" else [] for n in names}

        def find(self, frame, q):
            raise AssertionError("find_many should be used")

    room = Room([Thing("cup", 0.0, 15.0)])
    f = Finder(SimBody(room), Many())
    found = f.confirm("cup", 0.0, 15.0)
    assert asked[0] == also("cup") == ["cup", "mug", "coffee cup"]
    assert found and found.label == "cup"
