from __future__ import annotations

"""Optional QR/barcode detector.

Supports zxing-cpp first, then pyzbar fallback. It is intentionally optional and
bounded; missing packages produce a structured note instead of blocking import.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BarcodeFinding:
    kind: str
    text: str
    engine: str
    confidence: int = 0
    points: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BarcodeScanResult:
    available: bool = False
    executed: bool = False
    engine: str = "none"
    findings: list[BarcodeFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "executed": self.executed,
            "engine": self.engine,
            "findings": [item.to_dict() for item in self.findings],
            "warnings": list(self.warnings),
        }


def _safe_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "").strip()


def _dedupe(findings: list[BarcodeFinding], limit: int = 12) -> list[BarcodeFinding]:
    out: list[BarcodeFinding] = []
    seen: set[tuple[str, str]] = set()
    for item in findings:
        key = (item.kind.lower(), item.text)
        if not item.text or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def detect_barcodes(file_path: Path | str, *, max_dimension: int = 1600) -> BarcodeScanResult:
    path = Path(file_path)
    result = BarcodeScanResult()
    try:
        from PIL import Image
    except Exception:
        result.warnings.append("Pillow unavailable; barcode scan skipped.")
        return result

    try:
        import zxingcpp  # type: ignore
        result.available = True
        result.engine = "zxing-cpp"
        with Image.open(path) as image:
            image.load()
            image.thumbnail((max_dimension, max_dimension))
            decoded = zxingcpp.read_barcodes(image)
        findings: list[BarcodeFinding] = []
        for item in decoded or []:
            kind = _safe_text(getattr(item, "format", "barcode"))
            text = _safe_text(getattr(item, "text", ""))
            pos = getattr(item, "position", None)
            points: list[tuple[float, float]] = []
            if pos is not None:
                for point_name in ("top_left", "top_right", "bottom_right", "bottom_left"):
                    point = getattr(pos, point_name, None)
                    if point is not None and hasattr(point, "x") and hasattr(point, "y"):
                        points.append((float(point.x), float(point.y)))
            findings.append(BarcodeFinding(kind=kind, text=text[:1000], engine="zxing-cpp", confidence=90 if text else 0, points=points))
        result.executed = True
        result.findings = _dedupe(findings)
        return result
    except ImportError:
        pass
    except Exception as exc:
        result.warnings.append(f"zxing-cpp scan failed: {exc.__class__.__name__}.")

    try:
        from pyzbar.pyzbar import decode  # type: ignore
        result.available = True
        result.engine = "pyzbar"
        with Image.open(path) as image:
            image.load()
            image.thumbnail((max_dimension, max_dimension))
            decoded = decode(image)
        findings = []
        for item in decoded or []:
            points = [(float(p.x), float(p.y)) for p in getattr(item, "polygon", []) or [] if hasattr(p, "x") and hasattr(p, "y")]
            findings.append(BarcodeFinding(kind=_safe_text(getattr(item, "type", "barcode")), text=_safe_text(getattr(item, "data", b""))[:1000], engine="pyzbar", confidence=80 if getattr(item, "data", b"") else 0, points=points))
        result.executed = True
        result.findings = _dedupe(findings)
        return result
    except ImportError:
        result.warnings.append("No QR/barcode package installed; install zxing-cpp or pyzbar in the optional forensics stack.")
    except Exception as exc:
        result.warnings.append(f"pyzbar scan failed: {exc.__class__.__name__}.")
    return result
