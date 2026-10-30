-- RoadGuard SQLite Schema

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -------------------------------------------------------
-- images: one row per processed image file
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT    NOT NULL,
    filepath        TEXT    NOT NULL,
    upload_ts       TEXT    NOT NULL DEFAULT (datetime('now')),
    lat             REAL,
    lon             REAL,
    gps_source      TEXT,          -- 'exif' | 'manual' | NULL
    width_px        INTEGER,
    height_px       INTEGER,
    processed       INTEGER NOT NULL DEFAULT 0
);

-- -------------------------------------------------------
-- detections: one row per bounding-box detection
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS detections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id        INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    class_name      TEXT    NOT NULL,
    class_id        INTEGER NOT NULL,
    confidence      REAL    NOT NULL,
    bbox_x1         REAL    NOT NULL,
    bbox_y1         REAL    NOT NULL,
    bbox_x2         REAL    NOT NULL,
    bbox_y2         REAL    NOT NULL,
    bbox_area_ratio REAL    NOT NULL,
    severity_score  REAL    NOT NULL,
    segment_id      TEXT,          -- OSM way id (nullable if no GPS)
    detected_ts     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -------------------------------------------------------
-- road_segments: cached OSM road segment metadata
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS road_segments (
    segment_id      TEXT    PRIMARY KEY,   -- OSM way id as string
    name            TEXT,
    highway_type    TEXT,
    length_m        REAL,
    lat_start       REAL,
    lon_start       REAL,
    lat_end         REAL,
    lon_end         REAL,
    cached_ts       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -------------------------------------------------------
-- segment_aggregates: rolled-up scores per road segment
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS segment_aggregates (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id           TEXT    NOT NULL REFERENCES road_segments(segment_id),
    total_detections     INTEGER NOT NULL DEFAULT 0,
    max_severity         REAL    NOT NULL DEFAULT 0,
    mean_severity        REAL    NOT NULL DEFAULT 0,
    damage_density       REAL    NOT NULL DEFAULT 0,   -- detections per 100m
    priority_score       REAL    NOT NULL DEFAULT 0,   -- 0-100
    priority_label       TEXT    NOT NULL DEFAULT 'low',
    last_updated         TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -------------------------------------------------------
-- Indexes
-- -------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_detections_image    ON detections(image_id);
CREATE INDEX IF NOT EXISTS idx_detections_segment  ON detections(segment_id);
CREATE INDEX IF NOT EXISTS idx_aggregates_priority ON segment_aggregates(priority_score DESC);
