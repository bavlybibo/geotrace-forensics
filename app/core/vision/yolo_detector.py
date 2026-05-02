from __future__ import annotations

"""Optional Ultralytics YOLO object-detection bridge.

Disabled by default because model loading can be heavy. Enable with:
  GEOTRACE_YOLO_ENABLED=1
  GEOTRACE_YOLO_MODEL=C:\\path\\to\\yolov8n.pt  (or another local model)
"""

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class YoloDetectionResult:
    available: bool = False
    enabled: bool = False
    executed: bool = False
    model: str = "not configured"
    objects: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _enabled() -> bool:
    return os.getenv("GEOTRACE_YOLO_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def detect_objects_yolo(file_path: Path | str, *, max_results: int = 8) -> YoloDetectionResult:
    result = YoloDetectionResult(enabled=_enabled())
    try:
        from ultralytics import YOLO  # type: ignore
        result.available = True
    except Exception:
        result.warnings.append("ultralytics is not installed.")
        return result
    if not result.enabled:
        result.warnings.append("YOLO installed but disabled; set GEOTRACE_YOLO_ENABLED=1 and GEOTRACE_YOLO_MODEL to run local object detection.")
        return result
    model_ref = os.getenv("GEOTRACE_YOLO_MODEL", "").strip()
    if not model_ref:
        result.warnings.append("GEOTRACE_YOLO_MODEL is not configured; skipping model load to avoid accidental downloads.")
        return result
    result.model = model_ref
    try:
        model = YOLO(model_ref)
        predictions = model(str(file_path), verbose=False)
        objects: list[dict[str, Any]] = []
        for pred in predictions or []:
            names = getattr(pred, "names", {}) or {}
            boxes = getattr(pred, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                try:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = [float(x) for x in box.xyxy[0].tolist()]
                    label = str(names.get(cls_id, cls_id))
                    objects.append({"label": label, "confidence": round(conf * 100, 1), "box": [round(v, 2) for v in xyxy]})
                except Exception:
                    continue
        objects.sort(key=lambda item: -float(item.get("confidence", 0)))
        result.objects = objects[:max_results]
        result.executed = True
    except Exception as exc:
        result.warnings.append(f"YOLO execution failed: {exc.__class__.__name__}.")
    return result
