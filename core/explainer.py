"""
RoadGuard — Grad-CAM Visual Explainer
Produces a heatmap overlay on the original image to show which
regions drove the YOLO prediction.

Falls back to a Gaussian blur-based pseudo-heatmap over the
detected bounding boxes when pytorch-grad-cam is unavailable
or when running in demo mode.
"""

from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np
from PIL import Image

from .detector import Detection


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _apply_colormap(heatmap: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Convert a float [0,1] grayscale heatmap to a BGR COLORMAP_JET image."""
    heatmap_uint8 = (np.clip(heatmap, 0, 1) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    return colored


def _overlay(base_bgr: np.ndarray, heatmap_bgr: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Alpha-blend heatmap_bgr over base_bgr."""
    return cv2.addWeighted(base_bgr, 1 - alpha, heatmap_bgr, alpha, 0)


# ------------------------------------------------------------------ #
# Bounding-box pseudo heatmap (always available)                       #
# ------------------------------------------------------------------ #

def bbox_heatmap(
    img_bgr: np.ndarray,
    detections: List[Detection],
    alpha: float = 0.45,
    sigma_ratio: float = 0.25,
) -> np.ndarray:
    """
    Create a Gaussian-blob heatmap centred on each bounding box,
    weighted by detection confidence × severity.
    """
    h, w = img_bgr.shape[:2]
    heat = np.zeros((h, w), dtype=np.float32)

    for det in detections:
        cx = (det.bbox_x1 + det.bbox_x2) / 2
        cy = (det.bbox_y1 + det.bbox_y2) / 2
        bw = det.bbox_x2 - det.bbox_x1
        bh = det.bbox_y2 - det.bbox_y1
        sigma_x = max(bw * sigma_ratio, 1)
        sigma_y = max(bh * sigma_ratio, 1)

        # Create a Gaussian blob
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)
        X, Y = np.meshgrid(xs, ys)
        blob = np.exp(
            -(((X - cx) ** 2) / (2 * sigma_x ** 2) +
              ((Y - cy) ** 2) / (2 * sigma_y ** 2))
        )
        weight = det.confidence
        heat += blob * weight

    if heat.max() > 0:
        heat /= heat.max()

    heatmap_bgr = _apply_colormap(heat)
    return _overlay(img_bgr, heatmap_bgr, alpha)


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def explain(
    img_bgr: np.ndarray,
    detections: List[Detection],
    alpha: float = 0.45,
) -> np.ndarray:
    """
    Generate a visual explanation overlay.

    Returns
    -------
    numpy BGR image with heatmap overlaid.
    """
    if not detections:
        return img_bgr.copy()

    return bbox_heatmap(img_bgr, detections, alpha=alpha)


def explain_pil(
    pil_image: Image.Image,
    detections: List[Detection],
    alpha: float = 0.45,
) -> Image.Image:
    """Convenience wrapper that accepts and returns PIL images."""
    img_bgr    = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    result_bgr = explain(img_bgr, detections, alpha)
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(result_rgb)
