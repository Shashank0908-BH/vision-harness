from pathlib import Path

import cv2
import numpy as np
import pytest

from vision_harness.config import load_settings


@pytest.fixture
def image_path(tmp_path):
    image = np.full((100, 150, 3), 255, np.uint8)
    cv2.rectangle(image, (10, 20), (19, 29), (0, 0, 255), -1)
    cv2.rectangle(image, (60, 20), (79, 39), (0, 0, 255), -1)
    cv2.rectangle(image, (100, 50), (109, 59), (255, 0, 0), -1)
    path = tmp_path / "image.png"
    cv2.imwrite(str(path), image)
    return path


@pytest.fixture
def settings():
    return load_settings(Path("configs/poc.toml"))
