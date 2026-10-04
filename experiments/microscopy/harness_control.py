"""Run the exact harness StarDist adapter with fixed default settings, no labels/APIs.

Usage inside the specialist container: python /control.py /inputs /control-output
"""

import hashlib
import json
import sys
import time
from pathlib import Path

from vision_harness.artifacts import ArtifactStore
from vision_harness.contracts import Arguments, Step
from vision_harness.tools.stardist import execute


def run(inputs, output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / "results.json").exists():
        raise ValueError("Control results already exist; never overwrite inference")
    rows = []
    fields = {name: None for name in Arguments.model_fields}
    fields["segmentation_profile"] = "default"
    step = Step(
        step_id="segment", tool="stardist", input_ref="original", arguments=Arguments(**fields)
    )
    for path in sorted(inputs.glob("*.png")):
        store = ArtifactStore(output / path.stem)
        store.import_image(path)
        started = time.monotonic()
        evidence = execute(step, "original", "default", store)
        rows.append(
            {
                "id": path.stem,
                "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": "answered",
                "count": evidence.measurements["instance_count"],
                "elapsed_seconds": time.monotonic() - started,
                "evidence": evidence.model_dump(),
            }
        )
        print(path.stem + ": measured", flush=True)
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]))
