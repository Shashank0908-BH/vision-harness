"""Image artifacts retain pixel coordinates and origin across crops."""

import base64
import hashlib
from pathlib import Path

import cv2
import numpy as np

from .tracing import write_json


class ArtifactStore:
    def __init__(self, directory: Path, max_pixels: int = 16000000, max_bytes: int = 20000000):
        self.directory = directory / "artifacts"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_pixels, self.max_bytes = max_pixels, max_bytes
        self.records: dict[str, dict] = {}

    def import_image(self, path: Path) -> str:
        if path.stat().st_size > self.max_bytes:
            raise ValueError("Input image exceeds configured byte limit")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Cannot decode image; v1 supports ordinary raster images, not DICOM")
        return self.save(
            image, "original", source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )

    def save(self, image: np.ndarray, artifact_id: str, origin=(0, 0), **metadata) -> str:
        if image.size == 0 or image.shape[0] * image.shape[1] > self.max_pixels:
            raise ValueError("Image is empty or exceeds configured pixel limit")
        if (
            artifact_id in self.records
            or not artifact_id.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError("Artifact IDs must be unique and contain only letters, digits, - or _")
        path = self.directory / f"{artifact_id}.png"
        if not cv2.imwrite(str(path), image):
            raise ValueError("Failed to save image artifact")
        self.records[artifact_id] = {
            "path": str(path),
            "width": image.shape[1],
            "height": image.shape[0],
            "origin": list(origin),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            **metadata,
        }
        write_json(self.directory / "index.json", self.records)
        return artifact_id

    def load(self, artifact_id: str) -> np.ndarray:
        record = self.records[artifact_id]
        image = cv2.imread(record["path"], cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot read artifact {artifact_id}")
        return image

    def coordinates(self, artifact_id: str) -> dict:
        record = self.records[artifact_id]
        return {
            "units": "pixels",
            "origin": "top-left",
            "x_direction": "right",
            "y_direction": "down",
            "width": record["width"],
            "height": record["height"],
            "original_offset": record["origin"],
        }

    def image_input(self, artifact_id: str) -> dict:
        payload = Path(self.records[artifact_id]["path"]).read_bytes()
        return {
            "type": "input_image",
            "image_url": "data:image/png;base64," + base64.b64encode(payload).decode(),
            "detail": "high",
        }
