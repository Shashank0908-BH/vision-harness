"""Append-only observable events and inspectable provider call records."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if any(s in k.lower() for s in ("api_key", "authorization", "secret"))
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for name in ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "JEV_API_KEY"):
            secret = os.environ.get(name)
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(value), indent=2, allow_nan=False) + "\n")


class Trace:
    def __init__(self, directory: Path, observer: Callable | None = None):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.observer = observer
        self.sequence = 0
        self.before_call: Callable | None = None

    def emit(self, kind: str, data: dict) -> dict:
        self.sequence += 1
        event = redact(
            {
                "sequence": self.sequence,
                "time": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "data": data,
            }
        )
        with (self.directory / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(event, allow_nan=False) + "\n")
        if self.observer:
            self.observer(event)
        return event

    def call(self, provider: str, operation: str, request: dict) -> str:
        if self.before_call:
            self.before_call()
        call_id = f"call-{self.sequence + 1:04d}"
        write_json(self.directory / "calls" / f"{call_id}.request.json", request)
        self.emit(
            "call_started", {"call_id": call_id, "provider": provider, "operation": operation}
        )
        return call_id

    def response(self, call_id: str, response: dict, elapsed: float) -> None:
        write_json(self.directory / "calls" / f"{call_id}.response.json", response)
        self.emit(
            "call_finished",
            {"call_id": call_id, "elapsed_seconds": elapsed, "usage": response.get("usage")},
        )
