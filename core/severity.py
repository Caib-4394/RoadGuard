"""
RoadGuard — Severity Scoring
Maps per-detection attributes to a 0–10 severity score.

Formula
-------
    severity = base_class_weight × confidence × sqrt(bbox_area_ratio) × 10

Class weights reflect structural risk:
    alligator_crack    1.00  (worst — full surface failure)
    pothole            0.90  (high — vehicle damage risk)
    transverse_crack   0.70  (medium — water ingress)
    longitudinal_crack 0.55  (lower — slower progression)

The sqrt() on area ratio prevents very large boxes from dominating
while still rewarding coverage proportionally.
"""

from __future__ import annotations

import math
from typing import Dict

from .detector import Detection


# ------------------------------------------------------------------ #
# Weights                                                              #
# ------------------------------------------------------------------ #

CLASS_WEIGHTS: Dict[str, float] = {
    "alligator_crack":    1.00,
    "pothole":            0.90,
    "transverse_crack":   0.70,
    "longitudinal_crack": 0.55,
}

DEFAULT_CLASS_WEIGHT = 0.60


# ------------------------------------------------------------------ #
# Scoring                                                              #
# ------------------------------------------------------------------ #

def severity_score(det: Detection) -> float:
    """
    Return a severity score in [0, 10] for a single Detection.
    """
    weight     = CLASS_WEIGHTS.get(det.class_name, DEFAULT_CLASS_WEIGHT)
    area_factor = math.sqrt(max(det.bbox_area_ratio, 0.0))
    raw        = weight * det.confidence * area_factor * 10.0
    return round(min(max(raw, 0.0), 10.0), 3)


def score_all(detections: list[Detection]) -> list[float]:
    """Return a severity score for each detection in the list."""
    return [severity_score(d) for d in detections]


def severity_label(score: float) -> str:
    """Convert a numeric score to a human-readable label."""
    if score >= 7.5:
        return "critical"
    elif score >= 5.0:
        return "high"
    elif score >= 2.5:
        return "medium"
    else:
        return "low"


def severity_color(score: float) -> str:
    """Return a hex color for a severity score (for UI use)."""
    if score >= 7.5:
        return "#e63946"   # red
    elif score >= 5.0:
        return "#f4a261"   # orange
    elif score >= 2.5:
        return "#e9c46a"   # yellow
    else:
        return "#2a9d8f"   # green
