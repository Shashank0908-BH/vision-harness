"""The registered procedure is the unit of selection, not a model name."""

from typing import Literal

from pydantic import Field

from ..contracts import Record


class PinnedFile(Record):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Procedure(Record):
    plan_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    model: str
    checkpoint: str
    adapter: Literal["stardist", "cellpose"]
    python: str
    packages: dict[str, str]
    files: list[PinnedFile] = Field(min_length=1)
    task: Literal["count_nuclei"]
    modality: Literal["fluorescence"]
    input_conditions: list[str]
    parameters: dict
    sources: list[str]
    limitations: list[str]


class Catalog(Record):
    schema_version: Literal[1]
    version: str
    procedures: list[Procedure] = Field(min_length=1)


class Intent(Record):
    task: Literal["count_nuclei", "unsupported"]
    modality: Literal["fluorescence", "other", "unknown"]
    target: str
    rationale: str
    limitations: list[str]


class CandidateReason(Record):
    plan_id: str
    rationale: str
    assumptions: list[str]


class Proposal(Record):
    preferred_id: str
    candidates: list[CandidateReason]


class ScorableProcedure(Record):
    plan_id: str
    procedure: Procedure
    rationale: str
    assumptions: list[str]


class ResearchModel(Record):
    plan_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    model_name: str
    capability: str
    applicable_inputs: str
    checkpoint: str | None
    license: str | None
    hardware: str | None
    evidence: str
    limitations: list[str]
    sources: list[str] = Field(min_length=1)


class ResearchFindings(Record):
    proposals: list[ResearchModel] = Field(max_length=6)
    gaps: list[str]
