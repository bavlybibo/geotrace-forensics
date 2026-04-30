from __future__ import annotations

from typing import Iterable, Tuple


def ratio_to_float(value) -> float:
    """Convert EXIF/Pillow/GPS ratio values into floats.

    Different parsers represent DMS GPS values differently: exifread exposes
    Ratio objects with num/den, Pillow may expose IFDRational objects with
    numerator/denominator, and some images carry tuple/list pairs such as
    (num, den). A weak converter here causes valid GPS to be shown as missing,
    so keep this function deliberately tolerant.
    """
    if value is None:
        raise ValueError("GPS ratio value is None")
    if hasattr(value, "num") and hasattr(value, "den"):
        return float(value.num) / float(value.den or 1)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return float(value.numerator) / float(value.denominator or 1)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return float(value[0]) / float(value[1] or 1)
    if isinstance(value, str):
        cleaned = value.strip().strip("[]()")
        if "/" in cleaned:
            num, den = cleaned.split("/", 1)
            return float(num.strip()) / float(den.strip() or 1)
        return float(cleaned)
    return float(value)


def dms_to_decimal(values: Iterable, ref: str) -> float:
    values = list(values)
    if len(values) < 3:
        raise ValueError(f"GPS DMS sequence is incomplete: {values!r}")
    degrees = ratio_to_float(values[0])
    minutes = ratio_to_float(values[1])
    seconds = ratio_to_float(values[2])
    result = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if str(ref or "").upper().strip() in {"S", "W"}:
        result *= -1
    return round(result, 6)


def format_coordinates(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f}, {longitude:.6f}"


def coordinates_in_expected_range(latitude: float | None, longitude: float | None) -> bool:
    if latitude is None or longitude is None:
        return False
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def gps_confidence_summary(
    latitude: float | None,
    longitude: float | None,
    *,
    source: str = "Unavailable",
    altitude: float | None = None,
    exif_present: bool = False,
    source_type: str = "Unknown",
) -> Tuple[int, str]:
    if latitude is None or longitude is None:
        if source_type in {"Screenshot", "Messaging Export", "Screenshot / Export", "Graphic Asset"}:
            return 0, "No GPS recovered, which is normal for screenshots, exports, and graphic assets."
        return 0, "No native GPS recovered. Treat the file as non-geolocated unless external evidence provides location."

    if not coordinates_in_expected_range(latitude, longitude):
        return 18, "GPS tags were present but the decoded coordinates fall outside valid geographic ranges. Re-parse before relying on them."

    confidence = 92 if source == "Native EXIF" else 78
    bits = [f"GPS decoded from {source.lower()} tags"]
    if altitude is not None:
        bits.append(f"altitude {altitude:.2f} m available")
        confidence += 3
    if exif_present:
        bits.append("EXIF container present")
    if source_type in {"Edited / Exported", "Unknown"}:
        confidence -= 8
        bits.append("source workflow suggests checking whether coordinates survived export")
    if source_type in {"Messaging Export", "Screenshot", "Screenshot / Export"}:
        confidence -= 18
        bits.append("GPS in an export-like workflow deserves manual validation")
    confidence = max(20, min(98, confidence))
    return confidence, "; ".join(bits).capitalize() + "."
