"""OpenAI Responses adapter. Structured plans are the tool-command interface."""

import json
import time
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from ..config import Settings, require_key
from ..contracts import Answer, PlanSet
from ..tracing import Trace
from .transport import request as transport_request


class Astra:
    def __init__(self, settings: Settings, trace: Trace, client=None):
        self.settings, self.trace = settings, trace
        self.client = client or OpenAI(
            api_key=require_key("OPENAI_API_KEY"),
            timeout=settings.models.timeout_seconds,
            max_retries=0,
        )
        self.instructions = Path(settings.paths.astra_prompt).read_text()
        self.deadline = None

    def request_transport(self, operation, metadata, send):
        return transport_request(self.settings, self.trace, operation, metadata, send, self.deadline)

    def _request(self, operation: str, question: str, images: list, context: dict, schema):
        content = [
            {
                "type": "input_text",
                "text": json.dumps(
                    {"operation": operation, "question": question, "context": context}
                ),
            },
            *images,
        ]
        output_limit = self.settings.models.max_output_tokens
        instructions = self.instructions
        for attempt in range(self.settings.models.format_retries + 1):
            raw, call_id, start = self.request_transport(
                operation,
                {
                    "model": self.settings.models.astra,
                    "instructions": instructions,
                    "question": question,
                    "context": context,
                    "image_count": len(images),
                    "output_schema": schema.model_json_schema(),
                    "format_attempt": attempt + 1,
                    "max_output_tokens": output_limit,
                    "reasoning_effort": self.settings.models.reasoning_effort,
                },
                lambda timeout, instructions=instructions, output_limit=output_limit: self.client.responses.with_raw_response.parse(
                    model=self.settings.models.astra,
                    instructions=instructions,
                    input=[{"role": "user", "content": content}],
                    reasoning={"effort": self.settings.models.reasoning_effort},
                    max_output_tokens=output_limit,
                    text_format=schema,
                    store=False,
                    timeout=timeout,
                ),
            )
            data = raw.http_response.json()
            # Save raw response/usage even when SDK schema parsing fails.
            self.trace.response(call_id, data, time.monotonic() - start)
            reason = (data.get("incomplete_details") or {}).get("reason")
            if data.get("status") != "completed":
                if data.get("status") != "incomplete" or reason != "max_output_tokens":
                    raise ValueError(f"Astra response status={data.get('status')}; reason={reason}")
                failure = "max_output_tokens"
            else:
                try:
                    response = raw.parse()
                except ValidationError:
                    if attempt >= self.settings.models.format_retries:
                        raise
                    failure = "invalid_structured_output"
                else:
                    if response.output_parsed is None:
                        raise ValueError(
                            f"Astra returned no validated {schema.__name__}; refusal or missing output"
                        )
                    return response.output_parsed
            if attempt >= self.settings.models.format_retries:
                raise ValueError(f"Astra exhausted structured-output retries: {failure}")
            if failure == "max_output_tokens":
                output_limit = min(output_limit * 2, 32000)
            instructions = (
                self.instructions
                + "\nReturn complete, compact JSON matching the supplied schema. Avoid unnecessary whitespace."
            )
            self.trace.emit(
                "format_retry",
                {
                    "provider": "astra",
                    "failed_call_id": call_id,
                    "reason": failure,
                    "next_max_output_tokens": output_limit,
                    "next_attempt": attempt + 2,
                },
            )
        raise AssertionError("Unreachable structured response state")

    def structured(self, operation: str, question: str, images: list, context: dict, schema):
        """Use the same traced, bounded structured interface for registered workflows."""
        return self._request(operation, question, images, context, schema)

    def plan(self, question: str, images: list, context: dict) -> PlanSet:
        return self._request(
            "propose distinct eligible plans and your preferred plan",
            question,
            images,
            context,
            PlanSet,
        )

    def answer(self, question: str, images: list, context: dict) -> Answer:
        return self._request(
            "answer the question using available evidence", question, images, context, Answer
        )
