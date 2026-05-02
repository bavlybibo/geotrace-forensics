"""GeoTrace local vision runner template.

Replace the deterministic body with your local model call. The program receives
an image path as the last argument and must print JSON. It must not call the
network. Example models you can wire locally: BLIP/Florence for captioning,
YOLO/RT-DETR for objects, SigLIP/CLIP for similarity, or a custom map classifier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"warnings": ["missing image path"]}))
        return 2
    image_path = Path(sys.argv[-1])
    # This template is intentionally conservative. Replace this with real local
    # model inference and keep the same JSON schema.
    name = image_path.name.lower()
    is_map = any(token in name for token in ("map", "route", "gps", "location", "geo"))
    payload = {
        "provider": "geotrace-local-vision-template",
        "caption": "Map/navigation screenshot candidate" if is_map else "Local vision template output; wire your model here.",
        "scene_label": "map/navigation screenshot" if is_map else "unknown",
        "confidence": 0.62 if is_map else 0.25,
        "objects": [{"label": "map", "confidence": 0.62}] if is_map else [],
        "landmarks": [],
        "warnings": ["Template runner: replace with a real offline model before production use."],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
