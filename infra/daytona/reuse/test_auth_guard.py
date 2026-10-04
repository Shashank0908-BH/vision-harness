import asyncio
import json
from types import SimpleNamespace

import pytest

from infra.daytona.reuse.auth_guard import (
    AuthenticationGuard,
    ProviderAuthenticationFailure,
    authentication_failed,
)


@pytest.mark.parametrize("answer", [
    {"error_type": "AuthenticationError"},
    {"error_type": "HTTPStatusError", "error": "Jev HTTP 401: unauthorized"},
    {"error_type": "RuntimeError", "error": "Codex exit 1: token_invalidated"},
])
def test_authentication_errors_trip_guard(answer):
    assert authentication_failed(answer)


@pytest.mark.parametrize("answer", [
    {"status": "answered", "review_status": "provisional"},
    {"status": "abstained", "error": "Evidence insufficient"},
    {"error_type": "TimeoutError"},
    {"error_type": "HTTPStatusError", "error": "Jev HTTP 429"},
])
def test_scientific_outcomes_and_non_auth_errors_do_not_stop_cohort(answer):
    assert not authentication_failed(answer)


def test_serial_queue_stops_before_second_provider_call(tmp_path):
    async def run():
        guard = AuthenticationGuard(tmp_path / "job", tmp_path)
        semaphore = asyncio.Semaphore(1)
        calls = []

        async def trial(index):
            async with semaphore:
                event = SimpleNamespace(trial_name=f"trial-{index}")
                await guard.on_start(event)
                calls.append(index)
                path = tmp_path / "job" / event.trial_name / "agent/run/answer.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"error_type": "AuthenticationError"}))
                await guard.on_end(event)

        with pytest.raises(ExceptionGroup):
            async with asyncio.TaskGroup() as group:
                for index in range(36):
                    group.create_task(trial(index))
        assert calls == [0]
        assert (tmp_path / "job/trial-0/agent/run/answer.json").exists()
        assert json.loads((tmp_path / "authentication-stop.json").read_text())["failed_trial"] == "trial-0"
        with pytest.raises(ProviderAuthenticationFailure):
            await guard.on_start(SimpleNamespace(trial_name="later"))

    asyncio.run(run())
