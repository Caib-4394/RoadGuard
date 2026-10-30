"""
RoadGuard — OSMnx Road Segment Matcher
Downloads the road network around a GPS point and snaps
the point to the nearest road segment (OSM way edge).

Results are cached to disk as GraphML files to avoid
repeated network calls for the same area.
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ------------------------------------------------------------------ #
# Lazy imports so the module loads even without osmnx installed        #
# ------------------------------------------------------------------ #

_OSM_AVAILABLE = False
try:
    import osmnx as ox
    import networkx as nx
    from shapely.geometry import Point
    _OSM_AVAILABLE = True
except ImportError:
    pass

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "osm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Road class priority weights (used in priority scoring)
HIGHWAY_WEIGHTS: Dict[str, float] = {
    "motorway":     1.00,
    "trunk":        1.00,
    "primary":      0.80,
    "secondary":    0.60,
    "tertiary":     0.50,
    "residential":  0.40,
    "unclassified": 0.35,
    "service":      0.25,
}
DEFAULT_HIGHWAY_WEIGHT = 0.30

# Default search radius in metres
DEFAULT_RADIUS_M = 500


# ------------------------------------------------------------------ #
# Cache helpers                                                         #
# ------------------------------------------------------------------ #

def _cache_key(lat: float, lon: float, radius: int) -> str:
    blob = f"{lat:.5f}_{lon:.5f}_{radius}"
    return hashlib.md5(blob.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"graph_{key}.pkl"


def _load_cached(key: str):
    p = _cache_path(key)
    if p.exists():
        with open(p, "rb") as f:
            return pickle.load(f)
    return None


def _save_cache(key: str, graph) -> None:
    with open(_cache_path(key), "wb") as f:
        pickle.dump(graph, f)


# ------------------------------------------------------------------ #
# Graph retrieval                                                       #
# ------------------------------------------------------------------ #

def get_road_graph(lat: float, lon: float, radius_m: int = DEFAULT_RADIUS_M):
    """
    Return an OSMnx road graph centred on (lat, lon) within *radius_m* metres.
    Uses a local pickle cache; falls back gracefully if offline.
    """
    if not _OSM_AVAILABLE:
        return None

    key   = _cache_key(lat, lon, radius_m)
    graph = _load_cached(key)
    if graph is not None:
        return graph

    try:
        ox.settings.log_console = False
        graph = ox.graph_from_point(
            (lat, lon),
            dist=radius_m,
            network_type="drive",
            retain_all=False,
        )
        _save_cache(key, graph)
        return graph
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Segment matching                                                      #
# ------------------------------------------------------------------ #

def match_to_segment(
    lat: float,
    lon: float,
    graph=None,
    radius_m: int = DEFAULT_RADIUS_M,
) -> Optional[Dict[str, Any]]:
    """
    Find the nearest OSM road edge to (lat, lon).

    Returns a dict with segment metadata, or None if matching fails.
    """
    if not _OSM_AVAILABLE:
        return _synthetic_segment(lat, lon)

    if graph is None:
        graph = get_road_graph(lat, lon, radius_m)

    if graph is None:
        return _synthetic_segment(lat, lon)

    try:
        # Nearest edge returns (u, v, key, geom)
        u, v, key, data = ox.distance.nearest_edges(
            graph, X=lon, Y=lat, return_dist=False
        )
        edge_data = graph.edges[u, v, key]

        # Build segment id from OSM way id if available, else u-v pair
        osm_id = edge_data.get("osmid", f"{u}_{v}")
        if isinstance(osm_id, list):
            osm_id = osm_id[0]
        segment_id = str(osm_id)

        highway = edge_data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]

        # Start / end node coordinates
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]

        return {
            "segment_id":     segment_id,
            "name":           edge_data.get("name", "Unnamed Road"),
            "highway_type":   highway,
            "length_m":       edge_data.get("length", 0.0),
            "highway_weight": HIGHWAY_WEIGHTS.get(highway, DEFAULT_HIGHWAY_WEIGHT),
            "lat_start":      u_data.get("y"),
            "lon_start":      u_data.get("x"),
            "lat_end":        v_data.get("y"),
            "lon_end":        v_data.get("x"),
        }
    except Exception:
        return _synthetic_segment(lat, lon)


def _synthetic_segment(lat: float, lon: float) -> Dict[str, Any]:
    """Fallback synthetic segment when OSM is unavailable."""
    seg_id = f"synthetic_{lat:.4f}_{lon:.4f}"
    return {
        "segment_id":     seg_id,
        "name":           "Unknown Road",
        "highway_type":   "unclassified",
        "length_m":       100.0,
        "highway_weight": DEFAULT_HIGHWAY_WEIGHT,
        "lat_start":      lat,
        "lon_start":      lon,
        "lat_end":        lat + 0.001,
        "lon_end":        lon + 0.001,
    }


def highway_weight(highway_type: str) -> float:
    return HIGHWAY_WEIGHTS.get(highway_type, DEFAULT_HIGHWAY_WEIGHT)
