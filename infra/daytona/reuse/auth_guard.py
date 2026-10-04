"""Stop the serial Harbor queue after provider authentication fails, not low scores."""

import json
from datetime import datetime, timezone

from infra.daytona.reuse.common import write


class ProviderAuthenticationFailure(RuntimeError):
    pass


def authentication_failed(answer):
    if answer.get("error_type") == "AuthenticationError":
        return True
    error = str(answer.get("error") or "")
    return any(token in error for token in (
        "token_invalidated", "invalid_api_key", "Jev HTTP 401", "Error code: 401"))


class AuthenticationGuard:
    def __init__(self, job_dir, run):
        self.job_dir, self.run = job_dir, run
        self.failed_trial = None

    async def on_start(self, event):
        # A waiter may acquire Harbor's semaphore before TaskGroup cancellation.
        # START runs before any environment or provider work, so close that race.
        if self.failed_trial:
            raise ProviderAuthenticationFailure(f"Queue stopped after {self.failed_trial}")

    async def on_end(self, event):
        answer_path = self.job_dir / event.trial_name / "agent/run/answer.json"
        if not answer_path.exists():
            return
        answer = json.loads(answer_path.read_text())
        if not authentication_failed(answer):
            return
        self.failed_trial = event.trial_name
        write(self.run / "authentication-stop.json", {
            "stage": "blocked_authentication", "failed_trial": self.failed_trial,
            "stopped_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Provider authentication failed; subsequent trials must not call providers",
            "failed_trial_preserved": True, "workspace_kept_running": True,
        })
        # END follows Harbor's result write and environment cleanup. Propagate
        # through its TaskGroup so remaining pending trials are cancelled.
        raise ProviderAuthenticationFailure(f"Provider authentication failed in {self.failed_trial}")
