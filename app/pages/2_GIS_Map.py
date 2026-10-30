"""
RoadGuard — Page 2: GIS Map
Displays all detected damage on an interactive OpenStreetMap map
using Folium, with road segments color-coded by priority.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

from db.database import (
    query_all_images,
    query_all_segment_aggregates,
    query_all_detections,
)
from core.priority import priority_color, LABEL_COLORS

st.set_page_config(page_title="GIS Map — RoadGuard", page_icon="🗺️", layout="wide")

st.title("🗺️ GIS Map — Road Damage Overview")
st.caption("Damage locations plotted on OpenStreetMap. Road segments colored by maintenance priority.")

# ------------------------------------------------------------------ #
# Load data                                                            #
# ------------------------------------------------------------------ #

images     = query_all_images()
detections = query_all_detections()
aggregates = query_all_segment_aggregates()

# Filter images that have GPS
gps_images = [img for img in images if img["lat"] is not None and img["lon"] is not None]

# ------------------------------------------------------------------ #
# Sidebar filters                                                      #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.header("🗺️ Map Filters")
    priority_filter = st.multiselect(
        "Show priority levels",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
    )
    show_detection_markers = st.checkbox("Show image markers", value=True)
    show_segment_lines     = st.checkbox("Show road segment lines", value=True)

    st.divider()
    st.markdown(f"""
    **Legend**
    - 🔴 Critical (≥75)
    - 🟠 High (≥50)
    - 🟡 Medium (≥25)
    - 🟢 Low (<25)
    """)

# ------------------------------------------------------------------ #
# Folium color helper                                                  #
# ------------------------------------------------------------------ #


def _folium_color(hex_color: str) -> str:
    """Map hex priority color to a Folium color name."""
    mapping = {
        "#e63946": "red",
        "#f4a261": "orange",
        "#e9c46a": "beige",
        "#2a9d8f": "green",
    }
    return mapping.get(hex_color, "blue")


# ------------------------------------------------------------------ #
# Folium Map                                                           #
# ------------------------------------------------------------------ #

if not FOLIUM_OK:
    st.error("Folium or streamlit-folium is not installed. Run: `pip install folium streamlit-folium`")
    st.stop()

# Determine map center
if gps_images:
    center_lat = sum(img["lat"] for img in gps_images) / len(gps_images)
    center_lon = sum(img["lon"] for img in gps_images) / len(gps_images)
elif aggregates:
    center_lat = aggregates[0].get("lat_start") or 28.6139
    center_lon = aggregates[0].get("lon_start") or 77.2090
else:
    center_lat, center_lon = 28.6139, 77.2090   # Default: New Delhi

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=15,
    tiles="OpenStreetMap",
)

# ---- Road segment lines ------------------------------------------
if show_segment_lines:
    for agg in aggregates:
        label = agg.get("priority_label", "low")
        if label not in priority_filter:
            continue
        color = LABEL_COLORS.get(label, "#2a9d8f")
        lat_s = agg.get("lat_start")
        lon_s = agg.get("lon_start")
        lat_e = agg.get("lat_end")
        lon_e = agg.get("lon_end")
        if all(v is not None for v in [lat_s, lon_s, lat_e, lon_e]):
            popup_html = f"""
            <b>{agg.get('name','Unknown')}</b><br>
            Type: {agg.get('highway_type','N/A')}<br>
            Priority: <span style='color:{color}'>{agg.get('priority_score',0):.0f}/100 ({label.upper()})</span><br>
            Detections: {agg.get('total_detections',0)}<br>
            Max Severity: {agg.get('max_severity',0):.2f}<br>
            Mean Severity: {agg.get('mean_severity',0):.2f}
            """
            folium.PolyLine(
                locations=[[lat_s, lon_s], [lat_e, lon_e]],
                color=color,
                weight=6,
                opacity=0.85,
                tooltip=agg.get("name", "Road Segment"),
                popup=folium.Popup(popup_html, max_width=260),
            ).add_to(m)

# ---- Image / detection markers -----------------------------------
if show_detection_markers:
    for img in gps_images:
        img_dets = [d for d in detections if d["image_id"] == img["id"]]
        if not img_dets:
            # Simple marker for images with no detections
            folium.CircleMarker(
                location=[img["lat"], img["lon"]],
                radius=6,
                color="#2a9d8f",
                fill=True,
                fill_color="#2a9d8f",
                fill_opacity=0.8,
                tooltip=img["filename"],
                popup=folium.Popup(
                    f"<b>{img['filename']}</b><br>No damage detected", max_width=200
                ),
            ).add_to(m)
        else:
            max_sev = max(d.get("severity_score", 0) for d in img_dets)
            color   = priority_color(max_sev * 10)

            det_list = "".join(
                f"<li>{d['class_name'].replace('_',' ').title()} "
                f"({d['confidence']:.0%}) — sev {d['severity_score']:.2f}</li>"
                for d in img_dets
            )
            popup_html = f"""
            <b>{img['filename']}</b><br>
            GPS: {img['lat']:.5f}, {img['lon']:.5f}<br>
            Detections: {len(img_dets)}<br>
            <ul style='margin:4px 0 0 14px;padding:0;font-size:0.85em'>{det_list}</ul>
            """
            folium.Marker(
                location=[img["lat"], img["lon"]],
                icon=folium.Icon(color=_folium_color(color), icon="warning-sign", prefix="glyphicon"),
                tooltip=f"{img['filename']} ({len(img_dets)} detections)",
                popup=folium.Popup(popup_html, max_width=280),
            ).add_to(m)

# ---- Render map --------------------------------------------------
st_folium(m, width="100%", height=600, returned_objects=[])

# ---- Summary table below map ------------------------------------
if aggregates:
    st.subheader("📋 Segment Priority Summary")
    import pandas as pd
    df = pd.DataFrame([{
        "Road Name":      a.get("name", "Unknown"),
        "Highway Type":   a.get("highway_type", "N/A"),
        "Priority Score": a.get("priority_score", 0),
        "Priority":       a.get("priority_label", "low").upper(),
        "Detections":     a.get("total_detections", 0),
        "Max Severity":   a.get("max_severity", 0),
        "Mean Severity":  a.get("mean_severity", 0),
        "Damage/100m":    a.get("damage_density", 0),
    } for a in aggregates if a.get("priority_label") in priority_filter])

    if not df.empty:
        st.dataframe(
            df.sort_values("Priority Score", ascending=False),
            width="stretch",
            hide_index=True,
        )
else:
    st.info("No road segment data yet. Upload images with GPS on the **Upload & Detect** page.")
