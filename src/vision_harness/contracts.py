"""Shared, strict data contracts. This module has no provider or tool dependencies."""

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Arguments(Record):
    """One explicit argument shape keeps plans portable and reviewable."""

    color: Literal["red", "green", "blue", "any"] | None
    min_area: int | None = Field(ge=1, le=1000000)
    saturation_min: int | None = Field(ge=0, le=255)
    value_min: int | None = Field(ge=0, le=255)
    marker_fraction: float | None = Field(gt=0, lt=1)
    box: list[int] | None = Field(min_length=4, max_length=4)
    points: list[list[float]] | None = Field(min_length=2, max_length=2)
    segmentation_profile: Literal["default", "sensitive", "conservative"] | None = None

    @model_validator(mode="after")
    def validate_points(self):
        if self.points is not None and any(len(point) != 2 for point in self.points):
            raise ValueError("Each point must contain x and y")
        return self


class Step(Record):
    step_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
    tool: Literal["components", "watershed", "crop", "measure", "stardist"]
    input_ref: str
    arguments: Arguments


class CandidatePlan(Record):
    plan_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
    description: str
    assumptions: list[str]
    intended_output: str
    steps: list[Step] = Field(min_length=1, max_length=3)


class PlanSet(Record):
    observations: list[str]
    candidates: list[CandidatePlan] = Field(min_length=1, max_length=3)
    preferred_id: str

    @model_validator(mode="after")
    def unique_candidates(self):
        ids = [p.plan_id for p in self.candidates]
        if len(set(ids)) != len(ids) or self.preferred_id not in ids:
            raise ValueError("Plan IDs must be unique and preferred_id must name a candidate")
        return self


class Evidence(Record):
    evidence_id: str
    tool: str
    version: str
    input_artifact_id: str
    parameters: dict[str, Any]
    measurements: dict[str, Any]
    coordinate_system: dict[str, Any]
    artifact_ids: list[str]
    primary_artifact_id: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    status: Literal["success", "partial", "error"] = "success"


class Assessment(Record):
    plan_id: str
    score: float = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]


class Selection(Record):
    selected_ids: list[str]
    reason: str
    rejected: dict[str, str] = Field(default_factory=dict)


class Answer(Record):
    status: Literal["answered", "abstained", "error"]
    value: float | str | None
    explanation: str
    evidence_ids: list[str]
    limitations: list[str]


class ReviewCheck(Record):
    check_id: str
    support_probability: float = Field(ge=0, le=1)
    requirement: str
    remediation: str


class Review(Record):
    support_probability: float = Field(ge=0, le=1)
    checks: list[ReviewCheck] = Field(default_factory=list)


class AstraProvider(Protocol):
    def plan(self, question: str, images: list, context: dict) -> PlanSet: ...
    def answer(self, question: str, images: list, context: dict) -> Answer: ...


class JevProvider(Protocol):
    def assess(self, state: dict, candidates: list[CandidatePlan]) -> list[Assessment]: ...
    def review(self, state: dict) -> Review: ...
