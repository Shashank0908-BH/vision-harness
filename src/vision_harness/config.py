"""Configuration, paths and local secret loading. Never serializes secrets."""

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field

from .contracts import Record


class Models(Record):
    astra: str = "gpt-6-astra"
    jev: str = "jev-1.13.0"
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    max_output_tokens: int = Field(default=4096, ge=256, le=32000)
    format_retries: int = Field(default=1, ge=0, le=1)
    timeout_seconds: float = Field(default=120, gt=0)


class Limits(Record):
    max_rounds: int = Field(default=2, ge=1, le=5)
    max_steps_per_plan: int = Field(default=3, ge=1, le=3)
    max_candidates: int = Field(default=3, ge=1, le=3)
    max_pixels: int = Field(default=16000000, ge=1)
    max_input_bytes: int = Field(default=20000000, ge=1)
    jev_max_request_bytes: int = Field(default=24000, ge=4096, le=100000)


class SelectionConfig(Record):
    minimum_score: float = Field(default=1.5, ge=0, le=3)
    minimum_confidence: float = Field(default=0.5, ge=0, le=1)
    tie_margin: float = Field(default=0.25, ge=0, le=3)
    max_competing_plans: int = Field(default=2, ge=1, le=3)


class ReviewConfig(Record):
    minimum_support_probability: float = Field(default=0.75, ge=0, le=1)


class LoopConfig(Record):
    enabled: bool = False
    max_provider_calls: int = Field(default=24, ge=1, le=40)
    max_seconds: float = Field(default=600, gt=0, le=1000)
    max_no_progress_rounds: int = Field(default=1, ge=1, le=3)
    checks_path: str = "prompts/jev_review_checks.json"


class Paths(Record):
    runs: str = "runs"
    capabilities: str = "configs/capabilities.toml"
    astra_prompt: str = "prompts/astra.md"
    plan_rubric: str = "prompts/jev_plan_score.json"
    review_rubric: str = "prompts/jev_review.json"


class Settings(Record):
    models: Models = Field(default_factory=Models)
    limits: Limits = Field(default_factory=Limits)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    paths: Paths = Field(default_factory=Paths)


def load_settings(path: Path = Path("configs/poc.toml")) -> Settings:
    # Explicit project-relative paths are intentional; run from the repo or copied task bundle.
    # This local POC intentionally gives the project's .env precedence over inherited keys.
    load_dotenv(Path(".env"), override=True)
    return Settings.model_validate(tomllib.loads(path.read_text()))


def require_key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if name == "TYPESAFE_API_KEY":
        value = os.environ.get("JEV_API_KEY", "").strip() or value
    if not value:
        label = "JEV_API_KEY (or TYPESAFE_API_KEY)" if name == "TYPESAFE_API_KEY" else name
        raise ValueError(f"Missing {label}; set it in your local .env or environment")
    return value
