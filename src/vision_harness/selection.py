"""Explicit selection policy; Jev advises and Python enforces execution eligibility."""

from .config import SelectionConfig
from .contracts import Assessment, PlanSet, Selection
from .tools.registry import Registry


def select(
    plans: PlanSet,
    registry: Registry,
    max_steps: int,
    settings: SelectionConfig,
    assessments: list[Assessment] | None = None,
    excluded: dict[str, str] | None = None,
) -> Selection:
    eligible, rejected = [], {}
    for plan in plans.candidates:
        if excluded and plan.plan_id in excluded:
            rejected[plan.plan_id] = excluded[plan.plan_id]
            continue
        try:
            registry.validate(plan, max_steps)
            eligible.append(plan.plan_id)
        except ValueError as error:
            rejected[plan.plan_id] = str(error)
    if assessments is None:
        chosen = [plans.preferred_id] if plans.preferred_id in eligible else []
        return Selection(
            selected_ids=chosen,
            reason="Astra preference; no Jev selection"
            if chosen
            else "Astra preferred an ineligible plan",
            rejected=rejected,
        )
    by_id = {a.plan_id: a for a in assessments}
    if len(by_id) != len(assessments) or set(by_id) != set(eligible):
        raise ValueError("Jev must assess every eligible candidate exactly once")
    ranked = sorted((by_id[p] for p in eligible), key=lambda a: (-a.score, a.plan_id))
    viable = [a for a in ranked if a.score >= settings.minimum_score]
    if not viable:
        return Selection(
            selected_ids=[], reason="No plan met the configured fit threshold", rejected=rejected
        )
    best = viable[0]
    uncertain = best.confidence < settings.minimum_confidence
    close = [a for a in viable if best.score - a.score <= settings.tie_margin]
    pool = viable if uncertain else close
    chosen = pool[: settings.max_competing_plans]
    if uncertain and len(chosen) < 2:
        return Selection(
            selected_ids=[],
            reason="Low-confidence selection without a second viable plan; gather evidence or abstain",
            rejected=rejected,
        )
    return Selection(
        selected_ids=[a.plan_id for a in chosen],
        reason="Bounded comparison of uncertain/close candidates"
        if len(chosen) > 1
        else "Highest eligible Jev task-fit score",
        rejected=rejected,
    )
