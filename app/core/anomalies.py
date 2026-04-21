from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

from .models import EvidenceRecord


DATE_FORMATS = ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]


def parse_timestamp(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def dominant_device(records: Iterable[EvidenceRecord]) -> str:
    devices = [record.device_model for record in records if record.device_model not in {"Unknown", ""}]
    if not devices:
        return ""
    return Counter(devices).most_common(1)[0][0]


def detect_anomalies(record: EvidenceRecord, baseline_device: str, file_path: Path) -> Tuple[int, str, List[str]]:
    score = 0
    reasons: List[str] = []
    file_name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    screenshot_like = suffix in {".png", ".webp"} or "screenshot" in file_name or "whatsapp image" in file_name

    if not record.exif or len(record.exif) <= 1:
        if screenshot_like:
            score += 10
            reasons.append("Limited metadata is common for screenshots or exported chat images.")
        else:
            score += 25
            reasons.append("Metadata is missing or appears heavily stripped.")

    if record.timestamp == "Unknown":
        score += 10
        reasons.append("Timestamp could not be recovered from EXIF or filename.")
    elif screenshot_like and not record.exif:
        reasons.append("Timestamp was inferred from filename pattern due to limited embedded metadata.")

    if not record.has_gps:
        if not screenshot_like:
            score += 5
            reasons.append("No GPS coordinates were embedded in the image.")
        else:
            reasons.append("GPS is unavailable, which is typical for screenshots and messaging exports.")

    if record.software not in {"N/A", "", "Unknown"}:
        score += 8
        reasons.append(f"Software tag present: {record.software}.")

    if baseline_device and record.device_model not in {"Unknown", baseline_device}:
        score += 10
        reasons.append(f"Device differs from the dominant batch device ({baseline_device}).")

    if record.width and record.height and min(record.width, record.height) < 720:
        score += 4
        reasons.append("Relatively small dimensions compared with typical camera originals.")

    exif_dt = parse_timestamp(record.timestamp)
    if exif_dt and record.exif:
        file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
        if abs((file_dt - exif_dt).days) > 365:
            score += 8
            reasons.append("Filesystem modified time differs significantly from metadata time.")

    if score >= 60:
        level = "High"
    elif score >= 30:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No major metadata anomalies detected.")

    return min(score, 100), level, reasons
