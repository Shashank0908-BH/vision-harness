"""Lazy tool dispatch keeps specialist dependencies detachable."""

from . import opencv


def validate_step(step):
    if step.tool == "stardist":
        from .stardist import validate_step as validate

        return validate(step)
    return opencv.validate_step(step)


def execute(step, input_id, evidence_id, store):
    if step.tool == "stardist":
        from .stardist import execute as segment

        return segment(step, input_id, evidence_id, store)
    return opencv.execute(step, input_id, evidence_id, store)


def probe(store, specialist=False):
    if specialist:
        from .stardist import probe as inspect

        return inspect(store)
    return opencv.probe(store)
