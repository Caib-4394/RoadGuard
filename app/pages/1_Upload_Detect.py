"""
RoadGuard — Page 1: Upload & Detect
Handles image upload, runs the full pipeline, and displays results.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import streamlit as st
from PIL import Image

from core.pipeline import process_image
from core.priority import estimate_repair_window
from core.severity import severity_label, severity_color

st.set_page_config(page_title="Upload & Detect — RoadGuard", page_icon="📸", layout="wide")

st.markdown("""
<style>
.result-header {font-size:1.2rem; font-weight:700; margin-bottom:0.4rem;}
.det-row {background:#f8f9fa; border-radius:8px; padding:0.6rem 1rem; margin:0.3rem 0;}
</style>
""", unsafe_allow_html=True)

st.title("📸 Upload & Detect")
st.caption("Upload road images. The AI pipeline detects damage, scores severity, and maps to road segments.")

# ------------------------------------------------------------------ #
# Sidebar — GPS controls                                               #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.header("⚙️ Detection Settings")
    st.subheader("📍 GPS Override")
    use_manual_gps = st.checkbox("Enter GPS coordinates manually", value=False)
    manual_lat = manual_lon = None
    if use_manual_gps:
        manual_lat = st.number_input("Latitude",  value=28.6139, format="%.6f")
        manual_lon = st.number_input("Longitude", value=77.2090, format="%.6f")
        st.caption("💡 Coordinates will be used if image has no EXIF GPS data.")

    st.divider()
    st.subheader("🔍 Model Info")
    from core.pipeline import get_detector
    det = get_detector()
    if det.demo_mode:
        st.warning("⚠️ Running in **DEMO mode**.\nPlace a YOLOv8 `.pt` weights file in `data/models/` to enable real detection.")
    else:
        st.success("✅ YOLO model loaded")

# ------------------------------------------------------------------ #
# File uploader                                                         #
# ------------------------------------------------------------------ #

uploaded_files = st.file_uploader(
    "Choose road image(s)",
    type=["jpg", "jpeg", "png", "bmp", "webp"],
    accept_multiple_files=True,
)

shared_upload = st.session_state.get("roadguard_latest_upload")
if not uploaded_files and shared_upload is None:
    st.info("👆 Upload one or more road images to begin detection.")
    st.stop()

st.divider()

# ------------------------------------------------------------------ #
# Process each image                                                   #
# ------------------------------------------------------------------ #

analysis_items = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        pil_image = Image.open(uploaded_file).convert("RGB")
        with st.spinner(f"Running RoadGuard pipeline on {uploaded_file.name}…"):
            result = process_image(
                pil_image=pil_image,
                original_filename=uploaded_file.name,
                manual_lat=manual_lat,
                manual_lon=manual_lon,
            )
        analysis_items.append((uploaded_file.name, pil_image, result))
else:
    st.info(f"Showing the result for {shared_upload['filename']} uploaded on the dashboard. It was not processed again.")
    analysis_items.append((shared_upload["filename"], shared_upload["image"], shared_upload["result"]))

for filename, pil_image, result in analysis_items:
    st.markdown(f"### 🖼️ `{filename}`")

    detections      = result["detections"]
    detections_meta = result["detections_meta"]
    annotated_bgr   = result["annotated_image"]
    explained_pil   = result["explained_image"]
    lat             = result["lat"]
    lon             = result["lon"]
    gps_source      = result["gps_source"]
    aggregates      = result["aggregates"]

    # ---- Image panels -------------------------------------------- #
    col_orig, col_detect, col_explain = st.columns(3)

    with col_orig:
        st.markdown("**Original Image**")
        st.image(pil_image, width="stretch")

    with col_detect:
        st.markdown("**Detection Output**")
        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        st.image(annotated_rgb, width="stretch")

    with col_explain:
        st.markdown("**Visual Explanation (Heatmap)**")
        st.image(explained_pil, width="stretch")

    # ---- GPS info ------------------------------------------------- #
    if lat is not None:
        st.success(f"📍 GPS: `{lat:.6f}, {lon:.6f}` (source: **{gps_source}**)")
    else:
        st.warning("📍 No GPS coordinates available. Road segment matching skipped.")

    if result["demo_mode"]:
        st.info("ℹ️ **Demo Mode** — Bounding boxes are synthetic. Upload real YOLO weights to `data/models/` for live detection.")

    # ---- Summary cards -------------------------------------------- #
    priority_score = max((agg.get("priority_score", 0) for agg in aggregates.values()), default=0)
    priority_label = max((agg.get("priority_label", "low") for agg in aggregates.values()), key=lambda x: (x == "critical", x == "high", x == "medium", x == "low"), default="low") if aggregates else "low"
    repair_window = estimate_repair_window(priority_score)

    st.markdown("#### 🧾 Risk & Repair Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Priority Score", f"{priority_score:.0f}/100")
    with c2:
        st.metric("Risk Level", priority_label.title())
    with c3:
        st.metric("Repair Window", repair_window)

    # ---- Detections table ---------------------------------------- #
    st.markdown(f"**{len(detections)} detection(s) found**")

    if detections:
        import pandas as pd
        rows = []
        for i, (det, meta) in enumerate(zip(detections, detections_meta)):
            sev   = meta["severity_score"]
            rows.append({
                "#":             i + 1,
                "Damage Type":   det.class_name.replace("_", " ").title(),
                "Confidence":    f"{det.confidence:.1%}",
                "Severity":      f"{sev:.2f} / 10",
                "Severity Level":severity_label(sev).upper(),
                "Road Segment":  meta.get("name", "N/A"),
                "Highway Type":  meta.get("highway_type", "N/A"),
            })
        df = pd.DataFrame(rows)

        # Color-code severity column
        def highlight_severity(val):
            label = val.lower() if isinstance(val, str) else ""
            colors = {"critical": "#ffd6d6", "high": "#ffe8d6",
                      "medium": "#fff9d6", "low": "#d6f5f0"}
            bg = colors.get(label, "")
            return f"background-color: {bg}" if bg else ""

        styled = df.style.map(highlight_severity, subset=["Severity Level"])
        st.dataframe(styled, width="stretch", hide_index=True)
    else:
        st.success("✅ No damage detected in this image.")

    # ---- Segment priority cards ---------------------------------- #
    if aggregates:
        st.markdown("#### 🛣️ Road Segment Priority Scores")
        seg_cols = st.columns(min(len(aggregates), 3))
        for idx, (sid, agg) in enumerate(aggregates.items()):
            with seg_cols[idx % 3]:
                color = agg.get("priority_color", "#2a9d8f")
                label = agg.get("priority_label", "low").upper()
                score = agg.get("priority_score", 0)
                name  = agg.get("name", "Unknown Road")
                st.markdown(f"""
                <div style="border-left:5px solid {color}; background:#f8f9fa;
                            padding:0.8rem 1rem; border-radius:8px; margin-bottom:0.5rem;">
                    <b>{name}</b><br>
                    <span style="font-size:1.4rem; font-weight:700; color:{color};">{score:.0f}</span>
                    <span style="color:#666;"> / 100</span>
                    &nbsp;&nbsp;
                    <span style="background:{color}; color:white; padding:2px 8px;
                                 border-radius:10px; font-size:0.75rem;">{label}</span><br>
                    <small style="color:#888;">{agg.get('highway_type','').title()} · {agg.get('total_detections',0)} detections</small>
                </div>
                """, unsafe_allow_html=True)

    st.divider()
