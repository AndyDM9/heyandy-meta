import openai
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


class DeviceDown:
    """Glimmer isn't on this computer: what a judge's laptop has, with only a Model API key."""

    def chat(self, prompt, history=()):
        raise openai.APIConnectionError(request=None)

    def stream(self, prompt, history=()):
        raise openai.APIConnectionError(request=None)
        yield


def test_with_the_device_down_an_everyday_turn_goes_to_the_cloud_on_the_receipt(monkeypatch):
    monkeypatch.setenv("HEYANDY_PAID_CALLS", "1")
    receipts = []
    r = Router(DeviceDown(), MuseSparkModel(client=FakeClient("Paris.")), on_cloud=receipts.append)
    assert list(r.stream("What is the capital of France?")) == ["Paris."]
    assert r.last.where == "cloud" and "isn't answering" in r.last.reason
    assert receipts == ["What is the capital of France?"]
    assert r.answer("Good morning").text == "Paris." and receipts[-1] == "Good morning"


def test_with_the_device_down_and_no_way_to_the_cloud_the_error_stands(monkeypatch):
    monkeypatch.setenv("HEYANDY_PAID_CALLS", "1")
    cloud = FakeClient("never")
    receipts = []
    with pytest.raises(openai.APIError):  # no Model API key: no receipt to write, and it never hands over
        list(Router(DeviceDown(), MuseSparkModel(client=cloud)).stream("Good morning"))
    with pytest.raises(openai.APIError):  # offline
        list(Router(DeviceDown(), MuseSparkModel(client=cloud), on_cloud=receipts.append).stream("Good morning", online=False))
    assert cloud.calls == [] and receipts == []
    monkeypatch.delenv("HEYANDY_PAID_CALLS")
    with pytest.raises(openai.APIError):  # paid calls off: refused before anything was sent, so nothing on the receipt
        list(Router(DeviceDown(), MuseSparkModel(client=cloud), on_cloud=receipts.append).stream("Good morning"))
    assert cloud.calls == [] and receipts == []


def test_a_device_that_stops_half_way_isnt_started_again_by_the_cloud(monkeypatch):
    monkeypatch.setenv("HEYANDY_PAID_CALLS", "1")

    class Stops(DeviceDown):
        def stream(self, prompt, history=()):
            yield "Well."
            raise openai.APIConnectionError(request=None)

    cloud, got = FakeClient("never"), []
    with pytest.raises(openai.APIError):
        for sentence in Router(Stops(), MuseSparkModel(client=cloud), on_cloud=got.append).stream("Good morning"):
            got.append(sentence)
    assert got == ["Well."] and cloud.calls == []
