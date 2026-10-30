# 🛣️ RoadGuard — Road Damage Detection & Maintenance Prioritization

RoadGuard is an end-to-end AI system that:
- **Detects road damage** in images using YOLOv8 (pothole, cracks, alligator damage)
- **Scores severity** per detection (0–10 scale)
- **Maps damage to OSM road segments** via GPS coordinates
- **Prioritizes maintenance** with a composite score (0–100)
- **Visualizes everything** in an interactive Streamlit dashboard with GIS maps and CSV export
- **Plans road repairs** with configurable crew sizes, per-road worker assignments, completion estimates, and live dashboard refresh

---

## 📁 Project Structure

```
main project/
├── app/
│   ├── main.py                    # Home page
│   └── pages/
│       ├── 1_Upload_Detect.py     # Upload images & run detection
│       ├── 2_GIS_Map.py           # Interactive OSM map
│       └── 3_Export.py            # Reports & CSV download
├── core/
│   ├── detector.py                # YOLOv8 wrapper (demo mode if no weights)
│   ├── explainer.py               # Grad-CAM / heatmap overlay
│   ├── gps.py                     # EXIF GPS extraction & validation
│   ├── severity.py                # Per-detection severity scoring
│   ├── road_matcher.py            # OSMnx nearest road segment
│   ├── aggregator.py              # Segment-level aggregation
│   ├── priority.py                # Maintenance priority scoring
│   └── pipeline.py                # Full pipeline orchestrator
├── db/
│   ├── schema.sql                 # SQLite schema
│   └── database.py                # CRUD helpers
├── data/
│   ├── models/         ← Put your YOLO .pt weights here
│   ├── uploads/        ← Auto-populated on upload
│   └── osm_cache/      ← OSMnx graph cache
├── tests/
│   ├── test_detector.py
│   ├── test_severity.py
│   └── test_road_matcher.py
├── requirements.txt
└── run.bat             ← Double-click to launch on Windows
```

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. (Optional) Add YOLO weights
Place a YOLOv8 `.pt` weights file in `data/models/`.
- **Without weights**: the app runs in **demo mode** with synthetic detections.
- **With weights**: any YOLOv8 model works; for best results use weights trained on the [RDD2022](https://github.com/sekilab/RoadDamageDetector) dataset.

### 3. Launch the app
```bash
# Windows — double-click
run.bat

# Or from terminal:
streamlit run app/main.py --server.address 127.0.0.1 --server.port 8502
```

> If port `8501` is already in use, start the app on `8502` as shown above. The project launcher now defaults to `8502` to avoid the port conflict.

### Live repair planning
The home dashboard refreshes its saved detection and road-segment data every 15 seconds by default. Change the refresh interval or turn off **Live updates** to stop periodic refreshes. In **Road Crew Planner**, set the number of workers assigned to each road and see the estimated completion days update immediately. Other schedule views use the selected default crew size.

Completion days are planning estimates, scaled from a baseline four-worker crew using the road priority score; actual repair time depends on damage extent, materials, weather, and traffic management.

---

## 🧪 Run Tests
```bash
python -m pytest tests/ -v
```

---

## 📐 Scoring Formulas

### Severity Score (per detection, 0–10)
```
severity = class_weight × confidence × sqrt(bbox_area_ratio) × 10

Class weights:
  alligator_crack    1.00   ← highest structural risk
  pothole            0.90
  transverse_crack   0.70
  longitudinal_crack 0.55
```

### Maintenance Priority Score (per road segment, 0–100)
```
priority = [(max_severity/10 × 0.40)
          + (min(count/20, 1) × 0.30)
          + (highway_weight  × 0.30)] × 100

Priority labels:
  ≥75 → Critical 🔴
  ≥50 → High 🟠
  ≥25 → Medium 🟡
  < 25 → Low 🟢
```

---

## 🗺️ GPS & Road Matching
- GPS is read from **image EXIF metadata** automatically.
- A **manual lat/lon override** is available in the Upload page sidebar.
- When GPS is available, the system fetches the road graph from **OpenStreetMap** (via OSMnx) within a 500 m radius and snaps the detection to the nearest road segment.
- Road graphs are **cached locally** to `data/osm_cache/` to avoid repeated API calls.

---

## 🗃️ Database
All data is stored in `data/roadguard.db` (SQLite).
Tables: `images`, `detections`, `road_segments`, `segment_aggregates`.

---

## 📦 Key Dependencies
| Package | Purpose |
|---|---|
| `ultralytics` | YOLOv8 inference |
| `opencv-python-headless` | Image processing |
| `osmnx` | OpenStreetMap road graphs |
| `geopandas` / `shapely` | Geospatial operations |
| `streamlit` | Web dashboard |
| `folium` + `streamlit-folium` | Interactive maps |
| `plotly` | Charts |
| `pandas` | Data tables & CSV export |
