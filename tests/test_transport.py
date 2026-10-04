"""Transport recovery is bounded, observable and distinct from outcome retries."""

import json
import time

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from vision_harness.config import Settings
from vision_harness.providers import transport
from vision_harness.tracing import Trace


def test_transient_connection_retry_consumes_budget_and_preserves_failure(tmp_path, monkeypatch):
    settings = Settings()
    settings.models.transport_retries = 1
    trace = Trace(tmp_path)
    calls, waits, budgets = [], [], []
    trace.before_call = lambda: budgets.append(1)
    monkeypatch.setattr(transport.time, "sleep", waits.append)

    def send(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        return "ok"

    value, _, _ = transport.request(settings, trace, "test", {}, send, time.monotonic()+10)
    assert value == "ok" and len(calls) == len(budgets) == 2
    assert len(waits) == 1 and all(0 < t <= 10 for t in calls)
    assert len(list((tmp_path / "calls").glob("*.failure.json"))) == 1
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in events].count("transport_retry") == 1


@pytest.mark.parametrize("status,headers,body", [
    (401, {}, {}), (400, {}, {}),
    (429, {}, {"code": "insufficient_quota"}),
    (503, {"retry-after": "120"}, {}),
])
def test_nonrecoverable_errors_and_long_server_delays_are_not_retried(status, headers, body):
    response = httpx.Response(status, headers=headers, request=httpx.Request("POST", "https://api.openai.com"))
    error = APIStatusError("test", response=response, body=body)
    assert transport.retry_delay(error, 0) is None


def test_respects_server_delay():
    response = httpx.Response(503, headers={"retry-after": "7"}, request=httpx.Request("POST", "https://api.openai.com"))
    assert transport.retry_delay(APIStatusError("busy", response=response, body={}), 0) == 7


def test_no_request_starts_after_deadline(tmp_path):
    def send(timeout):
        pytest.fail("Deadline-expired request must not be sent")

    with pytest.raises(TimeoutError, match="No controller time"):
        transport.request(Settings(), Trace(tmp_path), "test", {}, send, time.monotonic()-1)
