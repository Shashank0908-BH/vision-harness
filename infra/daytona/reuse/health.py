"""Small real provider calls before launch; output contains no credential values."""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from openai import OpenAI


def astra():
    started = time.monotonic()
    with OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=45, max_retries=0) as client:
        response = client.responses.create(model="gpt-6-astra", input="Reply with OK.",
            reasoning={"effort": "low"}, max_output_tokens=128, store=False)
    if response.status != "completed" or not response.output_text:
        raise RuntimeError("Astra health response was incomplete")
    return {"provider": "astra", "passed": True, "seconds": round(time.monotonic()-started, 2)}


def jev():
    started = time.monotonic()
    key = os.environ.get("JEV_API_KEY") or os.environ["TYPESAFE_API_KEY"]
    with httpx.Client(timeout=45) as client:
        response = client.post("https://api.typesafe.ai/v1/systemone",
            headers={"Authorization": "Bearer " + key}, json={"model": "jev-1.13.0",
                "state": {"statement": "2 + 2 = 4"}, "questions": {"health": {
                    "type": "score", "instructions": "Score whether the arithmetic statement is correct.",
                    "criteria": ["Incorrect", "Correct"]}}})
    response.raise_for_status()
    if "health" not in response.json().get("answers", {}):
        raise RuntimeError("Jev health response omitted its answer")
    return {"provider": "jev", "passed": True, "seconds": round(time.monotonic()-started, 2)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda function: function(), (astra, jev)))
    args.output.write_text(json.dumps({"scope": "launch health only; not a benchmark trial", "providers": results}, indent=2))
    print(json.dumps({"providers_healthy": True}), flush=True)
