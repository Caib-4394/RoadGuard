"""
RoadGuard — GPS Utilities
Extracts GPS coordinates from image EXIF data and validates them.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


# ------------------------------------------------------------------ #
# EXIF extraction                                                      #
# ------------------------------------------------------------------ #

def _get_exif_data(image: Image.Image) -> dict:
    """Return raw EXIF dictionary from a PIL image, or empty dict."""
    try:
        raw = image._getexif()
        if raw is None:
            return {}
        return {TAGS.get(k, k): v for k, v in raw.items()}
    except Exception:
        return {}


def _dms_to_decimal(dms, ref: str) -> float:
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    def to_float(v):
        if isinstance(v, tuple):
            return v[0] / v[1] if v[1] else 0.0
        return float(v)

    degrees = to_float(dms[0])
    minutes = to_float(dms[1])
    seconds = to_float(dms[2])
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def extract_exif_gps(image_path: str | Path) -> Optional[Tuple[float, float]]:
    """
    Extract GPS (lat, lon) from image EXIF.

    Returns (lat, lon) as decimal degrees, or None if unavailable.
    """
    try:
        img = Image.open(str(image_path))
        exif = _get_exif_data(img)
        gps_info_raw = exif.get("GPSInfo")
        if not gps_info_raw:
            return None

        gps = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}

        lat_dms = gps.get("GPSLatitude")
        lat_ref = gps.get("GPSLatitudeRef", "N")
        lon_dms = gps.get("GPSLongitude")
        lon_ref = gps.get("GPSLongitudeRef", "E")

        if not (lat_dms and lon_dms):
            return None

        lat = _dms_to_decimal(lat_dms, lat_ref)
        lon = _dms_to_decimal(lon_dms, lon_ref)
        return lat, lon

    except Exception:
        return None


def extract_exif_gps_from_pil(pil_image: Image.Image) -> Optional[Tuple[float, float]]:
    """Same as extract_exif_gps but accepts an already-open PIL image."""
    try:
        exif = _get_exif_data(pil_image)
        gps_info_raw = exif.get("GPSInfo")
        if not gps_info_raw:
            return None

        gps = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}
        lat_dms = gps.get("GPSLatitude")
        lat_ref = gps.get("GPSLatitudeRef", "N")
        lon_dms = gps.get("GPSLongitude")
        lon_ref = gps.get("GPSLongitudeRef", "E")

        if not (lat_dms and lon_dms):
            return None

        lat = _dms_to_decimal(lat_dms, lat_ref)
        lon = _dms_to_decimal(lon_dms, lon_ref)
        return lat, lon
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Validation                                                           #
# ------------------------------------------------------------------ #

def validate_location(lat: float, lon: float) -> bool:
    """
    Basic sanity check on decimal-degree coordinates.
    Returns True if coordinates fall within valid geographic bounds.
    """
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def get_gps(
    image_path: Optional[str | Path],
    pil_image: Optional[object] = None,
    manual_lat: Optional[float] = None,
    manual_lon: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Resolve GPS coordinates with priority:
      1. Manual override (from UI)
      2. EXIF from PIL image
      3. EXIF from file path

    Returns (lat, lon, source) where source is 'manual', 'exif', or None.
    """
    # 1. Manual override
    if manual_lat is not None and manual_lon is not None:
        if validate_location(manual_lat, manual_lon):
            return manual_lat, manual_lon, "manual"

    # 2. PIL image EXIF
    if pil_image is not None:
        coords = extract_exif_gps_from_pil(pil_image)
        if coords and validate_location(*coords):
            return coords[0], coords[1], "exif"

    # 3. File path EXIF
    if image_path is not None:
        coords = extract_exif_gps(image_path)
        if coords and validate_location(*coords):
            return coords[0], coords[1], "exif"

    return None, None, None
