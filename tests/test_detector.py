"""
RoadGuard — Tests: Detector
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from PIL import Image

from core.detector import RoadDamageDetector, Detection, CLASS_NAMES


def _dummy_image() -> Image.Image:
    return Image.fromarray(np.zeros((480, 640, 3), dtype=np.uint8))


def test_demo_mode_returns_detections():
    det = RoadDamageDetector()
    assert det.demo_mode, "No weights present — should be in demo mode"
    pil = _dummy_image()
    detections, annotated = det.detect_pil(pil)
    assert len(detections) >= 1
    assert annotated.shape[2] == 3   # BGR image


def test_detection_fields():
    det = RoadDamageDetector()
    pil = _dummy_image()
    detections, _ = det.detect_pil(pil)
    for d in detections:
        assert isinstance(d, Detection)
        assert d.class_name in CLASS_NAMES.values()
        assert 0 < d.confidence <= 1.0
        assert 0.0 <= d.bbox_area_ratio <= 1.0


def test_detection_bbox_ordering():
    det = RoadDamageDetector()
    pil = _dummy_image()
    detections, _ = det.detect_pil(pil)
    for d in detections:
        assert d.bbox_x2 > d.bbox_x1
        assert d.bbox_y2 > d.bbox_y1
