"""
RoadGuard — Streamlit App Entry Point
"""

import hashlib
import sys
from pathlib import Path

# Make project root importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
from PIL import Image
import streamlit as st

from app.dashboard import render_maintenance_dashboard
from core.pipeline import process_image
from db.database import init_db

# ------------------------------------------------------------------ #
# Page config (must be first Streamlit call)                           #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="RoadGuard",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Bootstrap                                                            #
# ------------------------------------------------------------------ #

init_db()

# ------------------------------------------------------------------ #
# Custom CSS                                                           #
# ------------------------------------------------------------------ #

st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {background-color: #1a1a2e;}
    [data-testid="stSidebar"] * {color: #e0e0e0 !important;}

    /* Header */
    .roadguard-header {
        background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .roadguard-header h1 { margin: 0; font-size: 2.4rem; }
    .roadguard-header p  { margin: 0.4rem 0 0; opacity: 0.75; font-size: 1.05rem; }

    /* Metric cards */
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #0f3460;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }

    /* Severity badges */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        color: white;
    }
    .badge-critical { background: #e63946; }
    .badge-high     { background: #f4a261; }
    .badge-medium   { background: #e9c46a; color: #333; }
    .badge-low      { background: #2a9d8f; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Home page content                                                    #
# ------------------------------------------------------------------ #

st.markdown("""
<div class="roadguard-header">
    <h1>🛣️ RoadGuard</h1>
    <p>AI-Powered Road Damage Detection & Maintenance Prioritization System</p>
</div>
""", unsafe_allow_html=True)

st.subheader("Quick upload")
uploaded_file = st.file_uploader(
    "Upload a road image to detect damage",
    type=["jpg", "jpeg", "png", "bmp", "webp"],
    accept_multiple_files=False,
    key="main_upload",
)

latest_upload = st.session_state.get("roadguard_latest_upload")
if uploaded_file is not None:
    upload_bytes = uploaded_file.getvalue()
    upload_hash = hashlib.sha256(upload_bytes).hexdigest()
    if latest_upload is None or latest_upload["content_hash"] != upload_hash:
        pil_image = Image.open(uploaded_file).convert("RGB")
        with st.spinner(f"Processing {uploaded_file.name}…"):
            result = process_image(
                pil_image=pil_image,
                original_filename=uploaded_file.name,
                manual_lat=None,
                manual_lon=None,
            )
        latest_upload = {
            "content_hash": upload_hash,
            "filename": uploaded_file.name,
            "image": pil_image,
            "result": result,
        }
        st.session_state["roadguard_latest_upload"] = latest_upload

if latest_upload is not None:
    st.success(f"✅ Image uploaded and processed: {latest_upload['filename']}")

    col_orig, col_detect, col_explain = st.columns(3)
    with col_orig:
        st.markdown("**Original Image**")
        st.image(latest_upload["image"], width="stretch")

    with col_detect:
        st.markdown("**Detection Output**")
        annotated_rgb = cv2.cvtColor(latest_upload["result"]["annotated_image"], cv2.COLOR_BGR2RGB)
        st.image(annotated_rgb, width="stretch")

    with col_explain:
        st.markdown("**Visual Explanation**")
        st.image(latest_upload["result"]["explained_image"], width="stretch")

    st.page_link("pages/1_Upload_Detect.py", label="Open full detection report", icon="📸")
    st.divider()

st.subheader("Explore your results")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 📸 Upload & Detect
    View the full detection report for the image uploaded above, or upload a batch.
    """)
    st.page_link("pages/1_Upload_Detect.py", label="Open Upload & Detect", icon="📸")

with col2:
    st.markdown("""
    ### 🗺️ GIS Map
    Inspect detected damage on the map and compare road-segment priorities.
    """)
    st.page_link("pages/2_GIS_Map.py", label="Open GIS Map", icon="🗺️")

with col3:
    st.markdown("""
    ### 📊 Reports & Export
    Review saved detections and download the results as CSV.
    """)
    st.page_link("pages/3_Export.py", label="Open Reports & Export", icon="📊")

st.divider()

render_maintenance_dashboard()

st.markdown("""
---
> **Getting started:** Use the **sidebar** to navigate between pages.
> Upload a road image above to start a damage assessment.
""")
