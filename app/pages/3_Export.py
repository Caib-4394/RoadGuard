"""
RoadGuard — Page 3: Export & Reports
Browse all detections, filter, and download as CSV.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import io
import pandas as pd
import streamlit as st

from db.database import (
    query_all_detections,
    query_all_images,
    query_all_segment_aggregates,
)
from core.severity import severity_label, severity_color
from core.priority import priority_color, LABEL_COLORS

st.set_page_config(page_title="Export — RoadGuard", page_icon="📊", layout="wide")

st.title("📊 Reports & Export")
st.caption("Filter, inspect, and download all RoadGuard detection data.")

# ------------------------------------------------------------------ #
# Load data                                                            #
# ------------------------------------------------------------------ #

detections = query_all_detections()
images     = query_all_images()
aggregates = query_all_segment_aggregates()

# ------------------------------------------------------------------ #
# Tabs                                                                 #
# ------------------------------------------------------------------ #

summary_html = ""
if detections or aggregates:
    total_detections = len(detections)
    total_segments = len(aggregates)
    critical_segments = sum(1 for a in aggregates if str(a.get("priority_label", "low")).lower() == "critical")
    avg_severity = round(sum(float(d.get("severity_score", 0.0)) for d in detections) / total_detections, 2) if total_detections else 0.0
    top_road = max(aggregates, key=lambda a: float(a.get("priority_score", 0.0)), default={"name": "N/A", "priority_score": 0})
    top_name = top_road.get("name", "N/A")
    top_score = top_road.get("priority_score", 0)

    summary_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; padding: 24px; color: #1a1a1a;">
        <h2>RoadGuard Maintenance Summary</h2>
        <p><strong>Total detections:</strong> {total_detections}</p>
        <p><strong>Total road segments:</strong> {total_segments}</p>
        <p><strong>Critical segments:</strong> {critical_segments}</p>
        <p><strong>Average severity:</strong> {avg_severity}</p>
        <p><strong>Highest priority road:</strong> {top_name} ({top_score:.0f}/100)</p>
        <hr>
        <h3>Top priority roads</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
          <tr>
            <th>Road</th><th>Priority</th><th>Score</th><th>Detections</th>
          </tr>
          {''.join(
              f"<tr><td>{row.get('name', 'Unknown')}</td><td>{str(row.get('priority_label', 'low')).upper()}</td><td>{float(row.get('priority_score', 0.0)):.0f}</td><td>{row.get('total_detections', 0)}</td></tr>"
              for row in sorted(aggregates, key=lambda a: float(a.get('priority_score', 0.0)), reverse=True)[:5]
          )}
        </table>
      </body>
    </html>
    """

st.markdown("### 📄 Quick Summary Report")
if summary_html:
    st.download_button(
        label="⬇️ Download Maintenance Summary",
        data=summary_html,
        file_name="roadguard_summary_report.html",
        mime="text/html",
    )
else:
    st.info("No summary available yet. Upload images to generate a report.")


tab_det, tab_seg, tab_img = st.tabs([
    "🔍 All Detections",
    "🛣️ Segment Summary",
    "📷 Image Log",
])

# ================================================================== #
# TAB 1 — All Detections                                              #
# ================================================================== #

with tab_det:
    if not detections:
        st.info("No detections stored yet. Upload images on the **Upload & Detect** page.")
    else:
        df_det = pd.DataFrame(detections)

        # Sidebar filters
        with st.expander("🔧 Filters", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                class_filter = st.multiselect(
                    "Damage Type",
                    options=sorted(df_det["class_name"].unique()),
                    default=sorted(df_det["class_name"].unique()),
                )
            with col2:
                min_conf = st.slider("Min Confidence", 0.0, 1.0, 0.0, 0.05)
            with col3:
                min_sev  = st.slider("Min Severity Score", 0.0, 10.0, 0.0, 0.5)

        filtered = df_det[
            (df_det["class_name"].isin(class_filter)) &
            (df_det["confidence"] >= min_conf) &
            (df_det["severity_score"] >= min_sev)
        ].copy()

        filtered["Severity Level"] = filtered["severity_score"].apply(
            lambda v: severity_label(float(v)).upper() if pd.notna(v) else "LOW"
        )
        filtered["class_name"] = filtered["class_name"].apply(
            lambda v: str(v).replace("_", " ").title() if pd.notna(v) else "Unknown"
        )

        display_cols = [
            "id", "filename", "class_name", "confidence",
            "severity_score", "Severity Level", "segment_id",
            "upload_ts",
        ]
        display_cols = [c for c in display_cols if c in filtered.columns or c == "Severity Level"]

        st.markdown(f"**{len(filtered)} of {len(df_det)} detections shown**")
        st.dataframe(filtered[display_cols].rename(columns={
            "id": "Det #", "filename": "Image", "class_name": "Damage Type",
            "confidence": "Confidence", "severity_score": "Severity",
            "segment_id": "Segment ID", "upload_ts": "Timestamp",
        }), width="stretch", hide_index=True)

        # CSV download
        csv_bytes = filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv_bytes,
            file_name="roadguard_detections.csv",
            mime="text/csv",
        )

# ================================================================== #
# TAB 2 — Segment Summary                                             #
# ================================================================== #

with tab_seg:
    if not aggregates:
        st.info("No segment data yet.")
    else:
        df_seg = pd.DataFrame(aggregates)

        # Priority filter
        pf = st.multiselect(
            "Priority Filter",
            options=["critical", "high", "medium", "low"],
            default=["critical", "high", "medium", "low"],
        )
        df_seg_filtered = df_seg[df_seg["priority_label"].isin(pf)]

        display_seg = df_seg_filtered[[
            "name", "highway_type", "priority_score", "priority_label",
            "total_detections", "max_severity", "mean_severity",
            "damage_density", "length_m",
        ]].rename(columns={
            "name":              "Road Name",
            "highway_type":      "Type",
            "priority_score":    "Priority Score",
            "priority_label":    "Priority",
            "total_detections":  "Detections",
            "max_severity":      "Max Severity",
            "mean_severity":     "Mean Severity",
            "damage_density":    "Damage/100m",
            "length_m":          "Length (m)",
        }).sort_values("Priority Score", ascending=False)

        st.dataframe(display_seg, width="stretch", hide_index=True)

        csv_bytes = display_seg.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Segment Report CSV",
            data=csv_bytes,
            file_name="roadguard_segments.csv",
            mime="text/csv",
        )

        # Priority donut chart
        st.subheader("Priority Distribution")
        try:
            import plotly.express as px
            counts = df_seg["priority_label"].value_counts().reset_index()
            counts.columns = ["Priority", "Count"]
            color_map = {"critical": "#e63946", "high": "#f4a261",
                         "medium": "#e9c46a", "low": "#2a9d8f"}
            fig = px.pie(
                counts, names="Priority", values="Count",
                color="Priority", color_discrete_map=color_map,
                hole=0.4,
            )
            st.plotly_chart(fig, width="stretch")
        except ImportError:
            st.bar_chart(df_seg["priority_label"].value_counts())

# ================================================================== #
# TAB 3 — Image Log                                                   #
# ================================================================== #

with tab_img:
    if not images:
        st.info("No images processed yet.")
    else:
        df_img = pd.DataFrame(images)
        display_img = df_img[[
            "id", "filename", "upload_ts", "lat", "lon",
            "gps_source", "width_px", "height_px", "processed",
        ]].rename(columns={
            "id":        "Image #",
            "filename":  "Filename",
            "upload_ts": "Uploaded At",
            "lat":       "Latitude",
            "lon":       "Longitude",
            "gps_source":"GPS Source",
            "width_px":  "Width",
            "height_px": "Height",
            "processed": "Processed",
        })
        st.dataframe(display_img, width="stretch", hide_index=True)

        csv_bytes = display_img.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Image Log CSV",
            data=csv_bytes,
            file_name="roadguard_images.csv",
            mime="text/csv",
        )
