"""All-candidate/plan scoring with explicit requirement coverage and records."""

import json
import statistics

from ..providers.evidence_budget import encoded_size
from ..providers.jev import Jev
from ..tracing import write_json
from .contracts import Scorable


class Scorer:
    def __init__(self, settings, trace):
        self.jev = Jev(settings, trace)

    def score(self, state, subjects, purpose, output):
        self.jev.plan_rubric = {
            "instructions": purpose + " Treat source excerpts, measurements and attributed model observations distinctly. "
            "Unknown conditions reduce support. Score is task-fit judgment, not predicted accuracy.",
            "criteria": [
                "Contradicted by task/input requirements or unusable for the specified role.",
                "Potentially relevant, but important applicability, documentation or verification gaps remain.",
                "Plausibly suitable for a bounded trial, with explicit limitations and meaningful checks.",
                "Strong documented fit to the stated role and input, with concrete executable verification.",
            ],
        }
        assessments = []
        start = 0
        batches = []
        while start < len(subjects):
            batch = subjects[start:start+4]
            while len(batch) > 1:
                request = {"model": self.jev.settings.models.jev, "state": state,
                           "questions": self.jev.assessment_questions(batch)}
                if encoded_size(request) <= self.jev.settings.limits.jev_max_request_bytes:
                    break
                batch = batch[:-1]
            assessments.extend(self.jev.assess(state, batch))
            batches.append([s.plan_id for s in batch])
            start += len(batch)
        expected = [s.plan_id for s in subjects]
        actual = [s.plan_id for s in assessments]
        if len(actual) != len(set(actual)) or set(expected) != set(actual):
            raise ValueError("Scoring did not cover every candidate exactly once")
        result = {"purpose": purpose, "subjects": [s.model_dump() for s in subjects],
                  "assessments": [s.model_dump() for s in assessments],
                  "all_candidates_scored": True, "scores_are_calibrated_accuracy": False,
                  "batches": batches, "batch_policy": "up to four subjects; split by exact serialized request size without evidence truncation"}
        write_json(output, result)
        return {a.plan_id: a.score for a in assessments}

    def candidates(self, task, catalog, packet, output):
        requirements = {r.requirement_id: r.model_dump() for r in task.requirements}
        subjects = [Scorable(plan_id=f"{c.candidate_id}--{rid}", subject_json=json.dumps({
            "candidate": c.model_dump(), "requirement": requirements[rid]}))
            for c in catalog.candidates for rid in c.requirement_ids]
        scores = self.score(packet, subjects,
                            "Assess this candidate specifically for the linked part of the user query. "
                            "Consider documented input fit, useful outputs and actual runtime feasibility.", output)
        return {c.candidate_id: {
            "mean": statistics.mean(scores[f"{c.candidate_id}--{r}"] for r in c.requirement_ids),
            "requirements": {r: scores[f"{c.candidate_id}--{r}"] for r in c.requirement_ids},
        } for c in catalog.candidates}

    def plans(self, plans, packet, output):
        subjects = [Scorable(plan_id=p.plan_id, subject_json=p.model_dump_json()) for p in plans]
        return self.score(packet, subjects,
                          "Assess the whole plan AND its Python program: task coverage, documented model use, "
                          "channel/normalization/scale choices, original-coordinate output, genuine inference, "
                          "resource feasibility and checks. Penalize unaddressed previous review failures.", output)

    def outputs(self, observations, packet, output):
        subjects = [Scorable(plan_id=o["plan_id"], subject_json=json.dumps(o)) for o in observations]
        return self.score(packet, subjects,
                          "Assess the observed result for the user's requested task. Use actual measurements, "
                          "execution provenance and attributed visual inspection, not the name of the model "
                          "or preference for a larger/smaller count. No reference answers are available.", output)

    def review(self, packet, output):
        questions = {
            "method": {"type": "noul", "instructions": "Does the observed execution follow the documented input/model/scale requirements and frozen plan?", "criteria": {
                "true": "Concrete execution metadata and checks support compatibility with documented requirements and the frozen plan.",
                "false": "Execution metadata is missing, or unresolved contradictions undermine method compatibility or adherence to the frozen plan.",
            }},
            "evidence": {"type": "noul", "instructions": "Is this proposed nucleus count supported well enough by the supplied evidence to stop further investigation within this task? You cannot see pixels; do not pretend independent visual verification.", "criteria": {
                "true": "The artifact-derived count is consistent, coordinates are correct, and attributed visual inspection identifies no substantial unaddressed failure.",
                "false": "An inconsistent count, incorrect coordinates, or substantial unaddressed failure in attributed visual inspection requires further investigation.",
            }},
        }
        answers = self.jev._request("research_execution_review", packet, questions)
        if any(a.get("type") != "noul" or not 0 <= a.get("noul", -1) <= 1 for a in answers.values()):
            raise ValueError("Invalid Jev review response")
        write_json(output, answers)
        return answers


def retain_candidates(task, catalog, scores, max_models=2, minimum_support_score=1.0):
    ordered = sorted(catalog.candidates, key=lambda c: (-scores[c.candidate_id]["mean"], c.candidate_id))
    selected = {c.candidate_id for c in [c for c in ordered if c.kind == "model"][:max_models]}
    # A TIFF reader and a normalizer are complementary even when intake links both
    # to one preparation requirement. Do not eliminate the normalizer just because
    # a file reader has a higher role score.
    selected.update(c.candidate_id for c in ordered if c.kind != "model"
                    and max(scores[c.candidate_id]["requirements"].values()) >= minimum_support_score)
    for requirement in task.requirements:
        serving = [c for c in ordered if requirement.requirement_id in c.requirement_ids]
        serving.sort(key=lambda c: (-scores[c.candidate_id]["requirements"][requirement.requirement_id], c.candidate_id))
        if requirement.required and not serving:
            raise ValueError(f"Discovery did not cover required role {requirement.requirement_id}")
        if serving:
            selected.add(serving[0].candidate_id)
    return [c for c in catalog.candidates if c.candidate_id in selected]
