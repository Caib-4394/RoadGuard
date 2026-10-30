"""
RoadGuard — Tests: Road Matcher & Priority
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.road_matcher import _synthetic_segment, highway_weight, HIGHWAY_WEIGHTS
from core.priority import (
    maintenance_priority_score,
    priority_label,
    estimate_repair_window,
    estimate_repair_cost,
    recommended_action,
    crew_days_needed,
    estimated_completion_days,
    fallback_priority_from_detections,
    build_maintenance_plan,
    budget_summary_by_priority,
    schedule_repair_plan,
    assign_contractors,
    build_monthly_schedule,
)


def test_synthetic_segment_keys():
    seg = _synthetic_segment(28.6139, 77.2090)
    required = {"segment_id", "name", "highway_type", "length_m",
                "highway_weight", "lat_start", "lon_start", "lat_end", "lon_end"}
    assert required.issubset(seg.keys())


def test_highway_weight_known_types():
    assert highway_weight("motorway")    == 1.0
    assert highway_weight("primary")     == 0.80
    assert highway_weight("residential") == 0.40


def test_highway_weight_unknown():
    w = highway_weight("footway")
    assert 0.0 < w <= 1.0


def test_priority_score_range():
    agg = {"max_severity": 8.0, "total_detections": 10, "highway_weight": 0.8}
    score = maintenance_priority_score(agg)
    assert 0.0 <= score <= 100.0


def test_priority_label():
    assert priority_label(80)  == "critical"
    assert priority_label(55)  == "high"
    assert priority_label(30)  == "medium"
    assert priority_label(10)  == "low"


def test_priority_score_increases_with_severity():
    low  = maintenance_priority_score({"max_severity": 1.0, "total_detections": 1, "highway_weight": 0.3})
    high = maintenance_priority_score({"max_severity": 9.0, "total_detections": 5, "highway_weight": 0.8})
    assert high > low


def test_estimate_repair_window():
    assert estimate_repair_window(85) == "1-3 days"
    assert estimate_repair_window(60) == "4-7 days"
    assert estimate_repair_window(30) == "8-14 days"
    assert estimate_repair_window(10) == "15-21 days"


def test_repair_cost_and_action_plan():
    assert estimate_repair_cost(80) > 0
    assert recommended_action(80) == "Immediate repair"
    assert crew_days_needed(60) >= 2


def test_completion_estimate_scales_with_workers():
    assert estimated_completion_days(80, workers_per_crew=4) == 4
    assert estimated_completion_days(80, workers_per_crew=8) == 2
    assert estimated_completion_days(80, workers_per_crew=1) == 16


def test_fallback_priority_without_gps():
    fallback = fallback_priority_from_detections([
        {"class_name": "pothole", "severity_score": 8.0},
        {"class_name": "alligator_crack", "severity_score": 7.0},
    ])
    assert fallback["priority_score"] > 0
    assert fallback["priority_label"] in {"high", "critical"}


def test_build_maintenance_plan():
    plan = build_maintenance_plan([
        {"name": "Road A", "priority_score": 85, "highway_type": "primary"},
        {"name": "Road B", "priority_score": 30, "highway_type": "residential"},
    ])
    assert len(plan) == 2
    assert plan[0]["action"] == "Immediate repair"
    assert plan[1]["repair_window"] == "8-14 days"
    assert plan[0]["estimated_cost"] > 0
    assert plan[0]["workers_needed"] == 4


def test_worker_count_is_configurable_across_plans():
    segments = [{"name": "Road A", "priority_score": 85, "highway_type": "primary"}]
    assert build_maintenance_plan(segments, workers_per_crew=6)[0]["workers_needed"] == 6
    assert build_maintenance_plan(segments, workers_per_crew=6)[0]["completion_days"] == 3
    assert schedule_repair_plan(segments, workers_per_crew=6)[0]["workers_needed"] == 6
    assert schedule_repair_plan(segments, workers_per_crew=6)[0]["completion_days"] == 3
    assert assign_contractors(segments, workers_per_crew=6)[0]["workers_needed"] == 6
    assert assign_contractors(segments, workers_per_crew=6)[0]["completion_days"] == 3
    assert build_monthly_schedule(segments, workers_per_crew=6)[0]["workers_needed"] == 6
    assert build_monthly_schedule(segments, workers_per_crew=6)[0]["completion_days"] == 3


def test_budget_summary_by_priority():
    summary = budget_summary_by_priority([
        {"priority_score": 85, "priority_label": "critical"},
        {"priority_score": 60, "priority_label": "high"},
        {"priority_score": 30, "priority_label": "medium"},
        {"priority_score": 15, "priority_label": "low"},
    ])
    assert "critical" in summary
    assert summary["critical"]["segments"] == 1
    assert summary["critical"]["total_cost"] > 0
    assert sum(item["crew_days"] for item in summary.values()) > 0


def test_schedule_repair_plan():
    plan = schedule_repair_plan([
        {"name": "Road A", "priority_score": 90, "highway_type": "primary"},
        {"name": "Road B", "priority_score": 55, "highway_type": "residential"},
        {"name": "Road C", "priority_score": 25, "highway_type": "local"},
    ])
    assert len(plan) == 3
    assert plan[0]["week"] == 1
    assert plan[0]["priority_label"] in {"critical", "high", "medium", "low"}
    assert plan[0]["crew_days"] > 0


def test_assign_contractors():
    assignments = assign_contractors([
        {"name": "Road A", "priority_score": 90, "highway_type": "primary"},
        {"name": "Road B", "priority_score": 40, "highway_type": "residential"},
    ])
    assert len(assignments) == 2
    assert assignments[0]["team"] == "Emergency Response Crew"
    assert assignments[1]["team"] in {"Regional Maintenance Crew", "Routine Patrol Crew"}


def test_build_monthly_schedule():
    schedule = build_monthly_schedule([
        {"name": "Road A", "priority_score": 90, "highway_type": "primary"},
        {"name": "Road B", "priority_score": 55, "highway_type": "residential"},
        {"name": "Road C", "priority_score": 35, "highway_type": "local"},
    ], start_month=1)
    assert len(schedule) == 3
    assert schedule[0]["month"] in {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"}
    assert schedule[0]["crew_days"] > 0
