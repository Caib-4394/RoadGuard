"""
RoadGuard — YOLO Detector
Wraps YOLOv8 inference for road damage detection.

Classes (index → name):
  0: pothole
  1: longitudinal_crack
  2: transverse_crack
  3: alligator_crack

If no model weights are present the module runs in DEMO mode,
returning synthetic detections so the rest of the pipeline
can be exercised without a trained model.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

CLASS_NAMES = {
    0: "pothole",
    1: "longitudinal_crack",
    2: "transverse_crack",
    3: "alligator_crack",
}

CLASS_COLORS = {
    "pothole":             (220,  50,  50),   # red
    "longitudinal_crack":  (255, 165,   0),   # orange
    "transverse_crack":    (255, 215,   0),   # gold
    "alligator_crack":     (139,   0, 139),   # purple
}

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
DEFAULT_CONF_THRESHOLD = 0.25
DEFAULT_IOU_THRESHOLD  = 0.45
IMG_SIZE               = 640


# ------------------------------------------------------------------ #
# Data classes                                                         #
# ------------------------------------------------------------------ #

@dataclass
class Detection:
    class_id:       int
    class_name:     str
    confidence:     float
    bbox_x1:        float
    bbox_y1:        float
    bbox_x2:        float
    bbox_y2:        float
    bbox_area_ratio: float = field(init=False)
    image_width:    int    = 640
    image_height:   int    = 640

    def __post_init__(self):
        img_area  = max(self.image_width * self.image_height, 1)
        box_area  = (self.bbox_x2 - self.bbox_x1) * (self.bbox_y2 - self.bbox_y1)
        self.bbox_area_ratio = max(0.0, min(1.0, box_area / img_area))

    @property
    def color(self):
        return CLASS_COLORS.get(self.class_name, (128, 128, 128))


# ------------------------------------------------------------------ #
# Detector                                                             #
# ------------------------------------------------------------------ #

class RoadDamageDetector:
    """
    Loads a YOLOv8 model from *model_dir* (first *.pt file found).
    Falls back to DEMO mode (synthetic random detections) when no
    weights file is present.
    """

    def __init__(
        self,
        model_dir: Path = DEFAULT_MODEL_DIR,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD,
        iou_threshold:  float = DEFAULT_IOU_THRESHOLD,
    ) -> None:
        self.conf_threshold = conf_threshold
        self.iou_threshold  = iou_threshold
        self._model         = None
        self._demo_mode     = False
        self._load_model(model_dir)

    # ---- private -------------------------------------------------- #

    def _load_model(self, model_dir: Path) -> None:
        weights = sorted(model_dir.glob("*.pt"))
        if not weights:
            self._demo_mode = True
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(weights[0]))
            self._demo_mode = False
        except Exception as exc:          # ultralytics not installed yet
            self._demo_mode = True

    # ---- public --------------------------------------------------- #

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    def detect(self, image_path: str | Path) -> tuple[List[Detection], np.ndarray]:
        """
        Run detection on *image_path*.

        Returns
        -------
        detections : list of Detection objects
        annotated  : BGR numpy array with bounding boxes drawn
        """
        image_path = Path(image_path)
        img_bgr    = cv2.imread(str(image_path))
        if img_bgr is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        h, w = img_bgr.shape[:2]

        if self._demo_mode:
            detections = self._demo_detections(w, h)
        else:
            detections = self._yolo_detect(img_bgr, w, h)

        annotated = self._draw_boxes(img_bgr.copy(), detections)
        return detections, annotated

    def detect_pil(self, pil_image: Image.Image) -> tuple[List[Detection], np.ndarray]:
        """Accept a PIL image directly (used by Streamlit uploader)."""
        img_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        h, w   = img_bgr.shape[:2]

        if self._demo_mode:
            detections = self._demo_detections(w, h)
        else:
            detections = self._yolo_detect(img_bgr, w, h)

        annotated = self._draw_boxes(img_bgr.copy(), detections)
        return detections, annotated

    # ---- internals ------------------------------------------------ #

    def _yolo_detect(self, img_bgr: np.ndarray, w: int, h: int) -> List[Detection]:
        results = self._model.predict(
            img_bgr,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=IMG_SIZE,
            verbose=False,
        )
        detections = []
        for r in results:
            for box in r.boxes:
                cid  = int(box.cls.item())
                cname = CLASS_NAMES.get(cid, f"class_{cid}")
                conf  = float(box.conf.item())
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                det = Detection(
                    class_id=cid, class_name=cname, confidence=conf,
                    bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
                    image_width=w, image_height=h,
                )
                detections.append(det)
        return detections

    def _demo_detections(self, w: int, h: int) -> List[Detection]:
        """Generate 1–4 plausible fake detections for demo/testing."""
        random.seed(hash((w, h, os.getpid())) % (2**32))
        n = random.randint(1, 4)
        detections = []
        for _ in range(n):
            cid  = random.randint(0, 3)
            cname = CLASS_NAMES[cid]
            x1   = random.uniform(0.05 * w, 0.5 * w)
            y1   = random.uniform(0.05 * h, 0.5 * h)
            x2   = min(x1 + random.uniform(0.1 * w, 0.35 * w), w)
            y2   = min(y1 + random.uniform(0.1 * h, 0.35 * h), h)
            conf = random.uniform(0.45, 0.97)
            det  = Detection(
                class_id=cid, class_name=cname, confidence=conf,
                bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
                image_width=w, image_height=h,
            )
            detections.append(det)
        return detections

    def _draw_boxes(self, img: np.ndarray, detections: List[Detection]) -> np.ndarray:
        for det in detections:
            x1, y1, x2, y2 = (
                int(det.bbox_x1), int(det.bbox_y1),
                int(det.bbox_x2), int(det.bbox_y2),
            )
            color = det.color
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                img, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )
        return img
