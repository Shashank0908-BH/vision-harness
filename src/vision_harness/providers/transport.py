"""Bounded, individually traced retries for transient OpenAI transport failures."""

import math
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from openai import APIConnectionError, APIStatusError

from ..tracing import write_json


def retry_delay(error, attempt):
    if isinstance(error, APIStatusError):
        if getattr(error, "code", None) in {"insufficient_quota", "billing_hard_limit_reached"}:
            return None
        if error.status_code not in {408, 409, 429} and error.status_code < 500:
            return None
        headers = error.response.headers
        for name, divisor in (("retry-after-ms", 1000), ("retry-after", 1)):
            if name not in headers:
                continue
            try:
                delay = float(headers[name]) / divisor
            except ValueError:
                try:
                    date = parsedate_to_datetime(headers[name])
                    delay = (date - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError):
                    continue
            if math.isfinite(delay) and delay >= 0:
                # Never retry sooner than a server hint; decline long delays.
                return delay if delay <= 30 else None
    elif not isinstance(error, APIConnectionError):
        return None
    return 2**attempt + random.uniform(0, 1)


def request(settings, trace, operation, metadata, send, deadline=None):
    """send(timeout) performs one SDK request; SDK retries stay disabled."""
    for attempt in range(settings.models.transport_retries + 1):
        remaining = deadline - time.monotonic() if deadline is not None else float("inf")
        if remaining <= 1:
            raise TimeoutError("No controller time remains for a provider request")
        timeout = min(settings.models.timeout_seconds, remaining)
        call_id = trace.call("astra", operation, {
            **metadata, "transport_attempt": attempt + 1, "timeout_seconds": timeout})
        started = time.monotonic()
        try:
            return send(timeout), call_id, started
        except (APIConnectionError, APIStatusError) as error:
            failure = {"call_id": call_id, "error_type": type(error).__name__,
                       "error": str(error), "status_code": getattr(error, "status_code", None),
                       "elapsed_seconds": time.monotonic()-started}
            write_json(trace.directory / "calls" / f"{call_id}.failure.json", failure)
            trace.emit("call_failed", failure)
            delay = retry_delay(error, attempt)
            if attempt == settings.models.transport_retries or delay is None:
                raise
            if deadline is not None and deadline-time.monotonic() <= delay+1:
                raise
            trace.emit("transport_retry", {"failed_call_id": call_id, "delay_seconds": delay,
                                           "next_attempt": attempt+2})
            time.sleep(delay)
    raise AssertionError("Unreachable transport retry state")
