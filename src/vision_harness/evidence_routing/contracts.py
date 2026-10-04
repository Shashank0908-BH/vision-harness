"""Typed candidates separate measurements from attributed visual judgments."""

from typing import Literal

from pydantic import Field, model_validator

from ..contracts import Record


class Candidate(Record):
    plan_id: str
    kind: Literal["visual_estimate", "instance_measurement"]
    value: float = Field(ge=0)
    evidence_id: str
    model_family: str
    checkpoint: str | None
    parameters: dict
    measurements: dict
    limitations: list[str]
    provenance: dict

    @model_validator(mode="after")
    def integer_count(self):
        if not self.value.is_integer():
            raise ValueError("A nucleus count must be a finite nonnegative integer")
        return self


class Observation(Record):
    plan_id: str
    supporting_observations: list[str] = Field(max_length=6)
    concerns: list[str] = Field(max_length=6)


class Inspection(Record):
    observations: list[Observation] = Field(min_length=1, max_length=5)
    limitations: list[str] = Field(max_length=8)


class ObservedCandidate(Record):
    plan_id: str
    candidate: Candidate
    astra_visual_observations: Observation
