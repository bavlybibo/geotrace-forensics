from __future__ import annotations

"""Optional ImageHash bridge for near-duplicate/tamper triage."""

from pathlib import Path
from typing import Any


def compute_imagehashes(file_path: Path | str) -> dict[str, Any]:
    path = Path(file_path)
    try:
        from PIL import Image
        import imagehash  # type: ignore
    except Exception:
        return {"available": False, "method": "ImageHash", "warning": "ImageHash is not installed."}
    try:
        with Image.open(path) as image:
            image.load()
            base = image.convert("RGB")
            payload = {
                "available": True,
                "method": "ImageHash",
                "average_hash": str(imagehash.average_hash(base)),
                "perceptual_hash": str(imagehash.phash(base)),
                "difference_hash": str(imagehash.dhash(base)),
                "wavelet_hash": str(imagehash.whash(base)),
            }
            try:
                payload["colorhash"] = str(imagehash.colorhash(base))
            except Exception:
                pass
            return payload
    except Exception as exc:
        return {"available": True, "method": "ImageHash", "warning": f"ImageHash computation failed: {exc.__class__.__name__}."}
