"""Retry the Meta Model API's intermittent "model_not_found" 404s, then give up cleanly.

New accounts see the same request flip between success and 404 model_not_found (reported in the hackathon's
#questions, 2026-10-26/27; Meta is investigating). A few quick retries usually pass. When they don't, the caller
falls back to the models on this computer. Request IDs are kept so Meta can trace them; request bodies never are.
"""
import time

TRANSIENT_CODES = {"model_not_found"}


class CloudUnavailable(RuntimeError):
    def __init__(self, message: str, request_ids: list[str]):
        super().__init__(message)
        self.request_ids = request_ids


def _transient(err: Exception) -> bool:
    status = getattr(err, "status_code", None)
    code = getattr(err, "code", None)
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        code = code or body.get("code") or (body.get("error") or {}).get("code")
    return status == 404 and code in TRANSIENT_CODES or status in (429, 500, 502, 503, 504)


def with_retry(call, attempts: int = 3, delays=(0.4, 1.2), sleep=time.sleep):
    """Run ``call()``; retry transient cloud errors; raise CloudUnavailable after the last attempt."""
    request_ids = []
    for i in range(attempts):
        try:
            return call()
        except Exception as err:  # noqa: BLE001 - only transient errors are retried; the rest re-raise below
            if not _transient(err):
                raise
            request_ids.append(getattr(err, "request_id", None) or "?")
            if i < attempts - 1:
                sleep(delays[min(i, len(delays) - 1)])
    raise CloudUnavailable(f"the Meta Model API kept failing after {attempts} tries", request_ids)
