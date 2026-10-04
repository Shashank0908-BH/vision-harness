"""Synthetic renderer: labels come from scene construction, not our perception tools."""

import hashlib
import json
import math
import random
from pathlib import Path

import cv2
import numpy as np

from vision_harness.tracing import write_json


def generate(output: Path, dev=20, test=60, seed=20260922):
    if dev < 0 or test < 0 or dev + test == 0:
        raise ValueError("Dataset sizes must be nonnegative with at least one sample")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Dataset directory must be empty; use a new directory/version")
    (output / "images").mkdir(parents=True)
    rows = []
    palette = {"red": (0, 0, 220), "green": (0, 180, 0), "blue": (220, 0, 0)}
    for split, count in (("dev", dev), ("test", test)):
        rng = random.Random(f"{seed}-{split}")
        for index in range(count):
            case_id = hashlib.sha256(f"{seed}/{split}/{index}".encode()).hexdigest()[:12]
            image = np.full((384, 512, 3), 255, np.uint8)
            family = ("count", "color_count", "position", "distance", "touching_count")[index % 5]
            conditions = []
            if family in ("count", "color_count", "touching_count"):
                n = rng.randint(3, 12)
                slots = rng.sample(
                    [(x, y) for y in (65, 150, 235, 320) for x in (65, 155, 245, 335, 425)], n
                )
                colors = [
                    rng.choice(list(palette)) if family == "color_count" else "red" for _ in slots
                ]
                if family == "touching_count":
                    slots[0], slots[1] = (60, 60), (100, 60)
                    conditions.append("Two circles touch at one pixel; other circles are separated")
                    # Keep remaining circles away from the touching pair.
                    rest = [(x, y) for y in (150, 235, 320) for x in (65, 155, 245, 335, 425)]
                    slots[2:] = rng.sample(rest, n - 2)
                for point, color in zip(slots, colors, strict=True):
                    cv2.circle(image, point, 20, palette[color], -1)
                expected = colors.count("red")
                question = "How many red circles are in this image? Return the count as a number."
                tolerance = 0
            else:
                p1 = (rng.randint(60, 180), rng.randint(70, 310))
                p2 = (rng.randint(300, 450), rng.randint(70, 310))
                if family == "position" and rng.choice([True, False]):
                    p1, p2 = p2, p1
                cv2.circle(image, p1, 15, palette["red"], -1)
                cv2.circle(image, p2, 15, palette["blue"], -1)
                if family == "position":
                    expected = "left" if p1[0] < p2[0] else "right"
                    question = (
                        "Is the red circle left or right of the blue circle? Return left or right."
                    )
                    tolerance = 0
                else:
                    expected = math.dist(p1, p2)
                    tolerance = 2
                    question = "What is the Euclidean distance in pixels between the centers of the red and blue circles? Return a number."
            path = output / "images" / f"{case_id}.png"
            cv2.imwrite(str(path), image)
            rows.append(
                {
                    "id": case_id,
                    "split": split,
                    "family": family,
                    "image": f"images/{case_id}.png",
                    "question": question,
                    "expected": expected,
                    "tolerance": tolerance,
                    "conditions": conditions,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    (output / "manifest.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    write_json(
        output / "dataset.json",
        {
            "version": 1,
            "seed": seed,
            "dev": dev,
            "test": test,
            "label_source": "renderer scene parameters",
            "purpose": "narrow synthetic POC; not real-world validation",
        },
    )
