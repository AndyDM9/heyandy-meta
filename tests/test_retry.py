import pytest

from heyandy_meta.models.local_meta import GlimmerModel
from heyandy_meta.models.muse_spark import MuseSparkModel
from heyandy_meta.models.retry import CloudUnavailable, with_retry
from heyandy_meta.models.sam import Sam31Segmenter
from heyandy_meta.router import Router
from tests.fakes import FakeClient


class ApiError(Exception):
    def __init__(self, status, code, request_id="req_1"):
        super().__init__(f"{status} {code}")
        self.status_code, self.code, self.request_id = status, code, request_id


def flaky(failures, then="ok", status=404, code="model_not_found"):
    state = {"n": 0}

    def call():
        state["n"] += 1
        if state["n"] <= failures:
            raise ApiError(status, code, f"req_{state['n']}")
        return then
    return call, state


def test_a_flapping_404_is_retried_until_it_passes():
    call, state = flaky(2)
    assert with_retry(call, sleep=lambda s: None) == "ok" and state["n"] == 3


def test_giving_up_keeps_the_request_ids():
    call, _ = flaky(5)
    with pytest.raises(CloudUnavailable) as e:
        with_retry(call, sleep=lambda s: None)
    assert e.value.request_ids == ["req_1", "req_2", "req_3"]


def test_real_errors_are_not_retried():
    call, state = flaky(5, status=401, code="invalid_api_key")
    with pytest.raises(ApiError):
        with_retry(call, sleep=lambda s: None)
    assert state["n"] == 1


def test_when_the_cloud_stays_down_the_device_answers():
    class Down(FakeClient):
        def _create(self, **kw):
            raise ApiError(404, "model_not_found")

    r = Router(GlimmerModel(client=FakeClient("device")), MuseSparkModel(client=Down()))
    r_reply = r.answer("Can you explain this letter?")
    assert r_reply.source == "device" and r.last.reason.startswith("cloud unavailable")


def test_sam_retries_and_charges_only_once():
    from heyandy_meta.budget import Budget

    class Flaky(FakeClient):
        n = 0

        def _stream(self, **kw):
            Flaky.n += 1
            if Flaky.n == 1:
                raise ApiError(404, "model_not_found")
            return super()._stream(**kw)

    budget = Budget()
    Sam31Segmenter(client=Flaky(), budget=budget, sleep=lambda s: None).find(b"jpeg", "glasses")
    assert Flaky.n == 2 and budget.spent() == pytest.approx(0.0025)
