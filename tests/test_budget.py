import pytest

from heyandy_meta.budget import Budget, BudgetExceeded, chat_cost
from heyandy_meta.models.muse_spark import MuseSparkModel
from heyandy_meta.models.sam import Sam31Segmenter
from tests.fakes import FakeClient


def test_paid_calls_are_off_by_default(monkeypatch):
    monkeypatch.delenv("HEYANDY_PAID_CALLS")
    client = FakeClient()
    with pytest.raises(BudgetExceeded):
        MuseSparkModel(client=client).chat("hello")
    with pytest.raises(BudgetExceeded):
        Sam31Segmenter(client=client).find(b"jpeg", "glasses")
    assert client.calls == []  # refused before anything was sent


def test_each_call_is_recorded_at_list_price():
    budget = Budget()
    MuseSparkModel(client=FakeClient(), budget=budget).chat("hello")
    assert budget.spent() == pytest.approx(chat_cost("muse-spark-1.3", 1000, 100))  # $0.001675
    Sam31Segmenter(client=FakeClient(), budget=budget).find(b"jpeg", "glasses")
    assert budget.spent() == pytest.approx(0.001675 + 0.0025)


def test_the_cap_refuses_before_sending():
    budget = Budget(cap_usd=0.002)
    client = FakeClient()
    MuseSparkModel(client=client, budget=budget).chat("hello")
    with pytest.raises(BudgetExceeded):
        MuseSparkModel(client=client, budget=budget).chat("hello again")
    assert len(client.calls) == 1
