"""
RoadGuard — Full Pipeline Orchestrator
Ties together detection, GPS, severity scoring, road matching,
aggregation, priority scoring, and database persistence.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .detector   import RoadDamageDetector, Detection
from .explainer  import explain_pil
from .gps        import get_gps
from .severity   import severity_score
from .road_matcher import match_to_segment, get_road_graph, highway_weight
from .aggregator import aggregate_by_segment
from .priority   import score_aggregates, fallback_priority_from_detections

from db.database import (
    insert_image, mark_image_processed,
    insert_detection,
    upsert_road_segment,
    upsert_segment_aggregate,
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Shared detector instance (loaded once)
_detector: Optional[RoadDamageDetector] = None


def get_detector() -> RoadDamageDetector:
    global _detector
    if _detector is None:
        _detector = RoadDamageDetector()
    return _detector


# ------------------------------------------------------------------ #
# Main pipeline                                                         #
# ------------------------------------------------------------------ #

def process_image(
    pil_image: Image.Image,
    original_filename: str,
    manual_lat: Optional[float] = None,
    manual_lon: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run the full RoadGuard pipeline on a single PIL image.

    Returns
    -------
    result dict containing:
        image_id, detections, annotated_image, explained_image,
        lat, lon, gps_source, segment_info, aggregates
    """
    detector = get_detector()

    # 1. Save uploaded file to disk
    save_path = UPLOAD_DIR / original_filename
    pil_image.save(str(save_path))

    # 2. GPS resolution
    lat, lon, gps_source = get_gps(
        image_path=save_path,
        pil_image=pil_image,
        manual_lat=manual_lat,
        manual_lon=manual_lon,
    )

    # 3. Persist image record
    w, h     = pil_image.size
    image_id = insert_image(
        filename=original_filename,
        filepath=str(save_path),
        lat=lat, lon=lon,
        gps_source=gps_source,
        width_px=w, height_px=h,
    )

    # 4. YOLO Detection
    detections, annotated_bgr = detector.detect_pil(pil_image)

    # 5. Visual Explanation
    explained_pil = explain_pil(pil_image, detections)

    # 6. GPS-based road matching (if we have coordinates)
    graph       = None
    segment_map = {}   # detection_index → segment_info

    if lat is not None and lon is not None:
        graph = get_road_graph(lat, lon)

    # 7. Severity scoring + DB persistence
    detections_with_meta: List[Dict[str, Any]] = []

    for i, det in enumerate(detections):
        sev = severity_score(det)

        seg_info = None
        if lat is not None and lon is not None:
            seg_info = match_to_segment(lat, lon, graph)

        segment_id = seg_info["segment_id"] if seg_info else None

        # Persist road segment metadata
        if seg_info:
            upsert_road_segment(
                segment_id   = seg_info["segment_id"],
                name         = seg_info.get("name"),
                highway_type = seg_info.get("highway_type"),
                length_m     = seg_info.get("length_m"),
                lat_start    = seg_info.get("lat_start"),
                lon_start    = seg_info.get("lon_start"),
                lat_end      = seg_info.get("lat_end"),
                lon_end      = seg_info.get("lon_end"),
            )

        # Persist detection
        insert_detection(
            image_id        = image_id,
            class_name      = det.class_name,
            class_id        = det.class_id,
            confidence      = det.confidence,
            bbox_x1         = det.bbox_x1,
            bbox_y1         = det.bbox_y1,
            bbox_x2         = det.bbox_x2,
            bbox_y2         = det.bbox_y2,
            bbox_area_ratio = det.bbox_area_ratio,
            severity_score  = sev,
            segment_id      = segment_id,
        )

        meta = {
            "class_name":     det.class_name,
            "confidence":     det.confidence,
            "severity_score": sev,
            "segment_id":     segment_id,
            **(seg_info or {
                "segment_id":    None,
                "name":          "N/A",
                "highway_type":  "N/A",
                "length_m":      0.0,
                "highway_weight": 0.3,
                "lat_start":     lat, "lon_start": lon,
                "lat_end":       lat, "lon_end":   lon,
            }),
        }
        detections_with_meta.append(meta)
        segment_map[i] = seg_info

    # 8. Aggregation + Priority scoring
    aggregates = {}
    if detections_with_meta:
        if any(d["segment_id"] for d in detections_with_meta):
            filtered = [d for d in detections_with_meta if d["segment_id"]]
            raw_agg  = aggregate_by_segment(filtered)
            aggregates = score_aggregates(raw_agg)

            # Persist aggregates
            for sid, agg in aggregates.items():
                upsert_segment_aggregate(
                    segment_id       = sid,
                    total_detections = agg["total_detections"],
                    max_severity     = agg["max_severity"],
                    mean_severity    = agg["mean_severity"],
                    damage_density   = agg["damage_density"],
                    priority_score   = agg["priority_score"],
                    priority_label   = agg["priority_label"],
                )
        else:
            fallback = fallback_priority_from_detections(detections_with_meta)
            aggregates = {
                fallback["segment_id"]: {
                    "segment_id": fallback["segment_id"],
                    "name": fallback["name"],
                    "highway_type": fallback["highway_type"],
                    "highway_weight": 0.5,
                    "length_m": 100.0,
                    "total_detections": len(detections_with_meta),
                    "max_severity": max(float(d.get("severity_score", 0.0)) for d in detections_with_meta),
                    "mean_severity": sum(float(d.get("severity_score", 0.0)) for d in detections_with_meta) / len(detections_with_meta),
                    "damage_density": 0.0,
                    "priority_score": fallback["priority_score"],
                    "priority_label": fallback["priority_label"],
                    "priority_color": fallback["priority_color"],
                    "repair_window": fallback["repair_window"],
                }
            }

    mark_image_processed(image_id)

    return {
        "image_id":        image_id,
        "detections":      detections,
        "detections_meta": detections_with_meta,
        "annotated_image": annotated_bgr,
        "explained_image": explained_pil,
        "lat":             lat,
        "lon":             lon,
        "gps_source":      gps_source,
        "segment_map":     segment_map,
        "aggregates":      aggregates,
        "demo_mode":       detector.demo_mode,
    }
