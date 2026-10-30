"""
RoadGuard — Database Layer
Handles SQLite connection, table creation, and all CRUD operations.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

# Resolve DB path relative to this file
_BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = _BASE_DIR / "data" / "roadguard.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create all tables from schema.sql if they don't exist."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)


# ------------------------------------------------------------------
# Image CRUD
# ------------------------------------------------------------------

def insert_image(
    filename: str,
    filepath: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    gps_source: Optional[str] = None,
    width_px: Optional[int] = None,
    height_px: Optional[int] = None,
) -> int:
    """Insert a new image record. Returns the new image id."""
    sql = """
        INSERT INTO images (filename, filepath, lat, lon, gps_source, width_px, height_px)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, (filename, filepath, lat, lon, gps_source, width_px, height_px))
        conn.commit()
        return cur.lastrowid


def mark_image_processed(image_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE images SET processed = 1 WHERE id = ?", (image_id,))
        conn.commit()


def query_all_images() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM images ORDER BY upload_ts DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------
# Detection CRUD
# ------------------------------------------------------------------

def insert_detection(
    image_id: int,
    class_name: str,
    class_id: int,
    confidence: float,
    bbox_x1: float,
    bbox_y1: float,
    bbox_x2: float,
    bbox_y2: float,
    bbox_area_ratio: float,
    severity_score: float,
    segment_id: Optional[str] = None,
) -> int:
    sql = """
        INSERT INTO detections
            (image_id, class_name, class_id, confidence,
             bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             bbox_area_ratio, severity_score, segment_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, (
            image_id, class_name, class_id, confidence,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2,
            bbox_area_ratio, severity_score, segment_id,
        ))
        conn.commit()
        return cur.lastrowid


def query_detections_for_image(image_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM detections WHERE image_id = ?", (image_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def query_detections_by_segment(segment_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM detections WHERE segment_id = ?", (segment_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def query_all_detections() -> List[Dict[str, Any]]:
    sql = """
        SELECT d.*, i.filename, i.lat, i.lon, i.upload_ts
        FROM detections d
        JOIN images i ON d.image_id = i.id
        ORDER BY d.detected_ts DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------
# Road Segment CRUD
# ------------------------------------------------------------------

def upsert_road_segment(
    segment_id: str,
    name: Optional[str],
    highway_type: Optional[str],
    length_m: Optional[float],
    lat_start: Optional[float],
    lon_start: Optional[float],
    lat_end: Optional[float],
    lon_end: Optional[float],
) -> None:
    sql = """
        INSERT INTO road_segments
            (segment_id, name, highway_type, length_m,
             lat_start, lon_start, lat_end, lon_end)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(segment_id) DO UPDATE SET
            name         = excluded.name,
            highway_type = excluded.highway_type,
            length_m     = excluded.length_m,
            cached_ts    = datetime('now')
    """
    with get_connection() as conn:
        conn.execute(sql, (
            segment_id, name, highway_type, length_m,
            lat_start, lon_start, lat_end, lon_end,
        ))
        conn.commit()


# ------------------------------------------------------------------
# Segment Aggregate CRUD
# ------------------------------------------------------------------

def upsert_segment_aggregate(
    segment_id: str,
    total_detections: int,
    max_severity: float,
    mean_severity: float,
    damage_density: float,
    priority_score: float,
    priority_label: str,
) -> None:
    sql = """
        INSERT INTO segment_aggregates
            (segment_id, total_detections, max_severity, mean_severity,
             damage_density, priority_score, priority_label, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT DO UPDATE SET
            total_detections = excluded.total_detections,
            max_severity     = excluded.max_severity,
            mean_severity    = excluded.mean_severity,
            damage_density   = excluded.damage_density,
            priority_score   = excluded.priority_score,
            priority_label   = excluded.priority_label,
            last_updated     = datetime('now')
    """
    with get_connection() as conn:
        conn.execute(sql, (
            segment_id, total_detections, max_severity, mean_severity,
            damage_density, priority_score, priority_label,
        ))
        conn.commit()


def query_all_segment_aggregates() -> List[Dict[str, Any]]:
    sql = """
        SELECT sa.*, rs.name, rs.highway_type, rs.length_m,
               rs.lat_start, rs.lon_start, rs.lat_end, rs.lon_end
        FROM segment_aggregates sa
        JOIN road_segments rs ON sa.segment_id = rs.segment_id
        ORDER BY sa.priority_score DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]
