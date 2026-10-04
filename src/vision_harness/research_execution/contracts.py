"""Stage contracts: every decision links to a part of the original request."""

from typing import Literal

from pydantic import Field

from ..contracts import Record


class Requirement(Record):
    requirement_id: str
    purpose: str
    acceptance_check: str
    required: Literal[True]


class Task(Record):
    query: str
    task_type: Literal["nucleus_counting"]
    modality: str
    biological_target: str
    counting_rules: list[str]
    requirements: list[Requirement] = Field(min_length=3, max_length=8)
    observed_facts: list[str]
    assumptions: list[str]
    unknowns: list[str]


class Candidate(Record):
    candidate_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    kind: Literal["model", "library", "algorithm"]
    requirement_ids: list[str] = Field(min_length=1)
    capability: str
    version_or_checkpoint: str
    input_requirements: list[str]
    output_semantics: str
    deployment_requirements: list[str]
    license: str
    limitations: list[str]
    source_urls: list[str] = Field(min_length=1)
    documentation_urls: list[str] = Field(min_length=1)
    supported_claims: list[str]
    unknowns: list[str]


class Catalog(Record):
    candidates: list[Candidate] = Field(min_length=2, max_length=12)
    gaps: list[str]
    search_coverage: str


class UsageContract(Record):
    candidate_id: str
    source_ids: list[str]
    installation: list[str]
    supported_inputs: str
    channel_and_axis_rules: str
    normalization: str
    scale_and_resolution: str
    inference_api: str
    output_interpretation: str
    failure_modes: list[str]
    unresolved: list[str]
    ready_for_trial: bool


class UsageSet(Record):
    contracts: list[UsageContract]
    coverage_gaps: list[str]


class PlanStep(Record):
    step_id: str
    requirement_ids: list[str]
    candidate_ids: list[str]
    operation: str
    input_artifacts: list[str]
    output_artifacts: list[str]
    parameters_json: str
    checks: list[str]


class ExecutionPlan(Record):
    plan_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    summary: str
    candidate_ids: list[str] = Field(min_length=1)
    covered_requirement_ids: list[str]
    steps: list[PlanStep] = Field(min_length=3, max_length=10)
    setup_commands: list[str]
    python_program: str
    preprocessing_rationale: str
    usage_source_ids: list[str]
    limitations: list[str]


class PlanSet(Record):
    plans: list[ExecutionPlan] = Field(min_length=2, max_length=3)
    preferred_plan_id: str


class ExecutionOutcome(Record):
    status: Literal["executed", "needs_replan", "execution_error"]
    plan_id: str
    program_executed_unchanged: bool
    labels_path: str | None
    metadata_path: str | None
    setup_actions: list[str]
    failure_details: list[str]
    suggested_repair: str | None


class Inspection(Record):
    plan_id: str
    visual_observations: list[str]
    suspected_failures: list[str]
    checks_supported_by_artifacts: list[str]
    unresolved_requirements: list[str]
    recommended_action: Literal["finish", "replan", "research"]
    next_evidence_needed: list[str]


class ScalarAnswer(Record):
    status: Literal["answered", "abstained"]
    count: int | None = Field(ge=0)
    explanation: str
    limitations: list[str]


class Scorable(Record):
    plan_id: str
    subject_json: str


class Policy(Record):
    version: str = "research-execution-0.1"
    max_rounds: int = 2
    max_research_passes: int = 2
    max_provider_calls: int = 48
    max_seconds: int = 1500
    max_candidates: int = 12
    max_retained_models: int = 2
    minimum_support_candidate_score: float = 1.0
    max_document_pages_per_candidate: int = 3
    max_document_chars: int = 60000
    codex_timeout_seconds: int = 420
    review_support_threshold: float = 0.75
    max_no_progress_rounds: int = 1
