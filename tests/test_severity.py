"""
RoadGuard — Tests: Severity Scoring
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.detector import Detection
from core.severity import severity_score, severity_label, CLASS_WEIGHTS


def _make_det(class_name: str, confidence: float, area_ratio: float) -> Detection:
    # Create a synthetic detection with given parameters
    det = Detection.__new__(Detection)
    det.class_id        = 0
    det.class_name      = class_name
    det.confidence      = confidence
    det.bbox_x1         = 0
    det.bbox_y1         = 0
    det.bbox_x2         = 100
    det.bbox_y2         = 100
    det.image_width     = 640
    det.image_height    = 640
    det.bbox_area_ratio = area_ratio
    return det


def test_score_range():
    for cname in CLASS_WEIGHTS:
        det   = _make_det(cname, 0.85, 0.1)
        score = severity_score(det)
        assert 0.0 <= score <= 10.0, f"Score out of range for {cname}: {score}"


def test_alligator_worst():
    gator  = _make_det("alligator_crack",    0.90, 0.15)
    long_c = _make_det("longitudinal_crack", 0.90, 0.15)
    assert severity_score(gator) > severity_score(long_c)


def test_zero_confidence_gives_zero():
    det = _make_det("pothole", 0.0, 0.1)
    assert severity_score(det) == 0.0


def test_severity_labels():
    assert severity_label(8.0)  == "critical"
    assert severity_label(6.0)  == "high"
    assert severity_label(3.0)  == "medium"
    assert severity_label(1.0)  == "low"
