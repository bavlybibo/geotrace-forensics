from __future__ import annotations

"""Local-only image fingerprinting for OSINT/CTF image intelligence.

This module intentionally avoids network calls. It provides deterministic hashes and
small perceptual fingerprints that can support duplicate/near-duplicate triage and
future local landmark matching without uploading evidence.
"""

from pathlib import Path
from typing import Any


def fingerprint_image(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"available": False, "method": "local-luminance-8x8", "note": "Image path does not exist."}
    try:
        from PIL import Image
    except Exception:
        return {"available": False, "method": "local-luminance-8x8", "note": "Pillow is unavailable."}

    try:
        with Image.open(path) as image:
            small = image.convert("L").resize((8, 8))
            values = list(small.getdata())
    except Exception as exc:
        return {"available": False, "method": "local-luminance-8x8", "note": f"Fingerprint failed: {exc}"}

    avg = sum(values) / len(values)
    bits = "".join("1" if value >= avg else "0" for value in values)
    hex_value = f"{int(bits, 2):016x}"
    return {
        "available": True,
        "method": "local-luminance-8x8",
        "fingerprint": hex_value,
        "note": "Local-only image fingerprint; no external upload.",
    }
