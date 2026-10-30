"""
RoadGuard — Segment Aggregator
Groups detections by road segment and computes rolled-up statistics.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from .severity import severity_label


# ------------------------------------------------------------------ #
# Aggregation                                                          #
# ------------------------------------------------------------------ #

def aggregate_by_segment(
    detections_with_meta: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate a list of detection dicts (each containing
    'segment_id', 'severity_score', and road metadata)
    into per-segment statistics.

    Parameters
    ----------
    detections_with_meta : list of dicts with keys:
        segment_id, severity_score, highway_type, highway_weight,
        length_m, name, lat_start, lon_start, lat_end, lon_end

    Returns
    -------
    Dict[segment_id → aggregate_dict]
    """
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for det in detections_with_meta:
        sid = det.get("segment_id", "unknown")
        grouped[sid].append(det)

    aggregates: Dict[str, Dict[str, Any]] = {}
    for sid, dets in grouped.items():
        scores       = [d["severity_score"] for d in dets]
        max_sev      = max(scores)
        mean_sev     = sum(scores) / len(scores)
        length_m     = dets[0].get("length_m", 100.0) or 100.0
        density      = (len(dets) / length_m) * 100   # per 100 m
        hw_weight    = dets[0].get("highway_weight", 0.3)

        aggregates[sid] = {
            "segment_id":      sid,
            "name":            dets[0].get("name", "Unknown"),
            "highway_type":    dets[0].get("highway_type", "unclassified"),
            "highway_weight":  hw_weight,
            "length_m":        length_m,
            "lat_start":       dets[0].get("lat_start"),
            "lon_start":       dets[0].get("lon_start"),
            "lat_end":         dets[0].get("lat_end"),
            "lon_end":         dets[0].get("lon_end"),
            "total_detections": len(dets),
            "max_severity":    round(max_sev, 3),
            "mean_severity":   round(mean_sev, 3),
            "damage_density":  round(density, 3),
        }

    return aggregates
