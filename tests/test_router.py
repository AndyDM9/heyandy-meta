import pytest

from heyandy_meta.models.local_meta import GlimmerModel
from heyandy_meta.models.muse_spark import MuseSparkModel
from heyandy_meta.router import Router, decide
from tests.fakes import FakeClient


def router(cloud_client=None):
    return Router(GlimmerModel(client=FakeClient("device")), MuseSparkModel(client=cloud_client or FakeClient("cloud")))


@pytest.mark.parametrize("prompt, where", [
    ("Good morning, Andy", "device"),
    ("Where did I put my glasses?", "device"),
    ("Can you explain this letter from my bank?", "cloud"),
    ("Why do leaves change colour?", "cloud"),
    ("x" * 401, "cloud"),
])
def test_decide(prompt, where):
    assert decide(prompt).where == where


def test_offline_always_on_the_device():
    assert decide("Why do leaves change colour?", online=False) == decide("hi", online=False)
    assert router().answer("Why do leaves change colour?", online=False).source == "device"


def test_cloud_turn_uses_muse_spark_with_the_robot_rules():
    cloud = FakeClient("ok")
    r = router(cloud)
    assert r.answer("Explain tides").source == "cloud"
    assert cloud.calls[0]["model"] == "muse-spark-1.3"
    assert "robot" in cloud.calls[0]["messages"][0]["content"]


def test_cloud_refused_falls_back_to_the_device(monkeypatch):
    monkeypatch.delenv("HEYANDY_PAID_CALLS")
    r = router()
    assert r.answer("Can you explain this letter?").source == "device"
    assert r.last.reason.startswith("cloud refused")


def test_contributor_tier_is_refused():
    with pytest.raises(ValueError):
        MuseSparkModel(model="muse-spark-1.3-contributor")


def test_no_key_no_call(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        MuseSparkModel().chat("hello")
