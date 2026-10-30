"""
RoadGuard — Maintenance Priority Scorer

Formula
-------
    priority = (max_severity × 0.40)
             + (norm_count   × 0.30)
             + (hw_weight    × 0.30)
    × 10   →  score in [0, 100]

Where:
  max_severity  = max detection severity in segment   (0–10)
  norm_count    = min(detection_count / 20, 1.0)      (capped at 20)
  hw_weight     = road class weight                   (0–1)
"""

from __future__ import annotations

import math
from typing import Any, Dict


# ------------------------------------------------------------------ #
# Priority label thresholds                                            #
# ------------------------------------------------------------------ #

LABEL_THRESHOLDS = [
    (75, "critical"),
    (50, "high"),
    (25, "medium"),
    (0,  "low"),
]

LABEL_COLORS = {
    "critical": "#e63946",
    "high":     "#f4a261",
    "medium":   "#e9c46a",
    "low":      "#2a9d8f",
}

DAMAGE_TYPE_WEIGHTS = {
    "alligator_crack": 1.00,
    "pothole": 0.92,
    "transverse_crack": 0.72,
    "longitudinal_crack": 0.58,
    "unknown": 0.60,
}

DEFAULT_WORKERS_PER_CREW = 4


# ------------------------------------------------------------------ #
# Scoring                                                              #
# ------------------------------------------------------------------ #

def maintenance_priority_score(aggregate: Dict[str, Any]) -> float:
    """
    Compute maintenance priority score (0–100) for a road segment aggregate.
    """
    max_sev    = float(aggregate.get("max_severity",   0))
    count      = int  (aggregate.get("total_detections", 0))
    hw_weight  = float(aggregate.get("highway_weight", 0.3))

    norm_sev   = max_sev / 10.0
    norm_count = min(count / 20.0, 1.0)

    raw = (norm_sev * 0.40) + (norm_count * 0.30) + (hw_weight * 0.30)
    return round(min(max(raw, 0.0), 1.0) * 100, 2)


def priority_label(score: float) -> str:
    """Return human-readable priority label for a score in [0, 100]."""
    for threshold, label in LABEL_THRESHOLDS:
        if score >= threshold:
            return label
    return "low"


def priority_color(score: float) -> str:
    return LABEL_COLORS.get(priority_label(score), "#2a9d8f")


def estimate_repair_window(score: float) -> str:
    """Estimate the likely repair window in days based on maintenance priority."""
    if score >= 75:
        return "1-3 days"
    elif score >= 50:
        return "4-7 days"
    elif score >= 25:
        return "8-14 days"
    else:
        return "15-21 days"


def estimate_repair_cost(score: float, segment_count: int = 1) -> float:
    """Estimate a practical repair budget in USD from the segment priority score."""
    return round(max(float(score), 0.0) * 120.0 * max(segment_count, 1), 2)


def recommended_action(score: float) -> str:
    """Return a maintenance action label from the priority score."""
    if score >= 75:
        return "Immediate repair"
    elif score >= 50:
        return "Scheduled repair"
    elif score >= 25:
        return "Monitor and repair soon"
    return "Routine inspection"


def crew_days_needed(score: float) -> int:
    """Estimate the crew-days required for a repair job."""
    return max(1, int(round(max(float(score), 0.0) / 20.0)))


def estimated_completion_days(
    score: float, workers_per_crew: int = DEFAULT_WORKERS_PER_CREW
) -> int:
    """Estimate working days, scaling the baseline four-worker crew effort."""
    worker_count = max(1, int(workers_per_crew))
    worker_days = crew_days_needed(score) * DEFAULT_WORKERS_PER_CREW
    return max(1, math.ceil(worker_days / worker_count))


def build_maintenance_plan(
    segments: list[Dict[str, Any]], workers_per_crew: int = DEFAULT_WORKERS_PER_CREW
) -> list[Dict[str, Any]]:
    """Build a sorted action plan for road segments based on maintenance priority."""
    plan = []
    for segment in segments:
        score = float(segment.get("priority_score", 0.0))
        name = str(segment.get("name", "Unnamed Road"))
        highway_type = str(segment.get("highway_type", "unknown"))
        action = recommended_action(score)
        repair_window = estimate_repair_window(score)
        est_cost = estimate_repair_cost(score, segment_count=1)
        plan.append({
            "name": name,
            "highway_type": highway_type,
            "priority_score": score,
            "action": action,
            "repair_window": repair_window,
            "estimated_cost": est_cost,
            "crew_days": crew_days_needed(score),
            "workers_needed": max(1, int(workers_per_crew)),
            "completion_days": estimated_completion_days(score, workers_per_crew),
        })
    return sorted(plan, key=lambda item: item["priority_score"], reverse=True)


def budget_summary_by_priority(segments: list[Dict[str, Any]]) -> Dict[str, Dict[str, float | int]]:
    """Summarize total cost and crew-days by maintenance priority category."""
    summary: Dict[str, Dict[str, float | int]] = {
        "critical": {"total_cost": 0.0, "crew_days": 0, "segments": 0},
        "high": {"total_cost": 0.0, "crew_days": 0, "segments": 0},
        "medium": {"total_cost": 0.0, "crew_days": 0, "segments": 0},
        "low": {"total_cost": 0.0, "crew_days": 0, "segments": 0},
    }

    for segment in segments:
        score = float(segment.get("priority_score", 0.0))
        label = str(segment.get("priority_label", priority_label(score))).lower()
        if label not in summary:
            label = priority_label(score)
        if label not in summary:
            continue

        cost = estimate_repair_cost(score, segment_count=1)
        days = crew_days_needed(score)
        summary[label]["total_cost"] += cost
        summary[label]["crew_days"] += days
        summary[label]["segments"] += 1

    return {k: v for k, v in summary.items() if v["segments"] > 0}


def schedule_repair_plan(
    segments: list[Dict[str, Any]], workers_per_crew: int = DEFAULT_WORKERS_PER_CREW
) -> list[Dict[str, Any]]:
    """Return a simple work schedule assigning segments to weekly repair slots."""
    sorted_segments = sorted(
        segments,
        key=lambda item: float(item.get("priority_score", 0.0)),
        reverse=True,
    )
    schedule = []
    for index, segment in enumerate(sorted_segments, start=1):
        score = float(segment.get("priority_score", 0.0))
        label = str(segment.get("priority_label", priority_label(score))).lower()
        if label not in {"critical", "high", "medium", "low"}:
            label = priority_label(score)
        schedule.append({
            "name": str(segment.get("name", "Unnamed Road")),
            "priority_score": score,
            "priority_label": label,
            "crew_days": crew_days_needed(score),
            "workers_needed": max(1, int(workers_per_crew)),
            "completion_days": estimated_completion_days(score, workers_per_crew),
            "week": ((index - 1) // 2) + 1,
            "repair_window": estimate_repair_window(score),
        })
    return schedule


def assign_contractors(
    segments: list[Dict[str, Any]], workers_per_crew: int = DEFAULT_WORKERS_PER_CREW
) -> list[Dict[str, Any]]:
    """Assign each segment to a contractor or crew team based on urgency."""
    team_map = {
        "critical": "Emergency Response Crew",
        "high": "Regional Maintenance Crew",
        "medium": "Regional Maintenance Crew",
        "low": "Routine Patrol Crew",
    }
    assignments = []
    for segment in sorted(segments, key=lambda item: float(item.get("priority_score", 0.0)), reverse=True):
        score = float(segment.get("priority_score", 0.0))
        label = str(segment.get("priority_label", priority_label(score))).lower()
        if label not in team_map:
            label = priority_label(score)
        assignments.append({
            "name": str(segment.get("name", "Unnamed Road")),
            "priority_score": score,
            "priority_label": label,
            "team": team_map.get(label, "Routine Patrol Crew"),
            "crew_days": crew_days_needed(score),
            "workers_needed": max(1, int(workers_per_crew)),
            "completion_days": estimated_completion_days(score, workers_per_crew),
        })
    return assignments


def build_monthly_schedule(
    segments: list[Dict[str, Any]],
    start_month: int = 1,
    workers_per_crew: int = DEFAULT_WORKERS_PER_CREW,
) -> list[Dict[str, Any]]:
    """Build a month-based maintenance schedule from the priority-ranked list."""
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    sorted_segments = sorted(
        segments,
        key=lambda item: float(item.get("priority_score", 0.0)),
        reverse=True,
    )
    schedule = []
    for index, segment in enumerate(sorted_segments, start=1):
        score = float(segment.get("priority_score", 0.0))
        month_index = (int(start_month) - 1 + ((index - 1) // 2)) % 12
        schedule.append({
            "name": str(segment.get("name", "Unnamed Road")),
            "priority_score": score,
            "priority_label": str(segment.get("priority_label", priority_label(score))).lower(),
            "month": month_names[month_index],
            "repair_window": estimate_repair_window(score),
            "crew_days": crew_days_needed(score),
            "workers_needed": max(1, int(workers_per_crew)),
            "completion_days": estimated_completion_days(score, workers_per_crew),
        })
    return schedule


def fallback_priority_from_detections(detections_with_meta: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a usable risk summary when GPS/road matching is unavailable."""
    if not detections_with_meta:
        return {
            "priority_score": 0.0,
            "priority_label": "low",
            "priority_color": "#2a9d8f",
            "repair_window": estimate_repair_window(0),
            "segment_id": "gps_unavailable",
            "name": "GPS Unavailable",
            "highway_type": "unknown",
        }

    weighted_scores = []
    for det in detections_with_meta:
        class_name = str(det.get("class_name", "unknown")).lower()
        severity = float(det.get("severity_score", 0.0))
        type_weight = DAMAGE_TYPE_WEIGHTS.get(class_name, DAMAGE_TYPE_WEIGHTS["unknown"])
        weighted_scores.append(severity * type_weight)

    avg_weighted_severity = sum(weighted_scores) / len(weighted_scores)
    count_factor = min(len(weighted_scores) / 4.0, 1.0)
    score = min(100.0, round((avg_weighted_severity / 10.0) * 70.0 + count_factor * 30.0, 2))

    label = priority_label(score)
    return {
        "priority_score": score,
        "priority_label": label,
        "priority_color": priority_color(score),
        "repair_window": estimate_repair_window(score),
        "segment_id": "gps_unavailable",
        "name": "GPS Unavailable",
        "highway_type": "unknown",
    }


def score_aggregates(
    aggregates: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Enrich each aggregate dict with priority_score and priority_label.
    Returns the updated dict.
    """
    for sid, agg in aggregates.items():
        ps = maintenance_priority_score(agg)
        agg["priority_score"] = ps
        agg["priority_label"] = priority_label(ps)
        agg["priority_color"] = priority_color(ps)
    return aggregates
