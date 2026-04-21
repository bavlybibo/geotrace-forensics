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


def assign_duplicate_groups(records: List[EvidenceRecord]) -> None:
    buckets: dict[str, List[EvidenceRecord]] = {}
    for record in records:
        buckets.setdefault(record.perceptual_hash, []).append(record)
    group_index = 1
    for phash, items in buckets.items():
        if len(items) > 1 and phash != "0" * 16:
            group = f"Cluster-{group_index:02d}"
            for item in items:
                item.duplicate_group = group
            group_index += 1


def detect_anomalies(record: EvidenceRecord, baseline_device: str, file_path: Path) -> Tuple[int, int, str, List[str]]:
    score = 0
    confidence = 60
    reasons: List[str] = []
    source_type = record.source_type

    if not record.exif:
        if source_type in {"Screenshot", "Messaging Export", "Screenshot / Export"}:
            score += 8
            confidence += 10
            reasons.append("Embedded metadata is limited, which is common for screenshots or messaging exports.")
        else:
            score += 24
            reasons.append("No embedded EXIF metadata was recovered from the file.")

    if record.timestamp == "Unknown":
        score += 15
        reasons.append("Timestamp could not be recovered from EXIF, filename, or filesystem fallback.")
        confidence -= 10
    elif record.timestamp_source == "Filename Pattern":
        score += 3
        confidence += 4
        reasons.append("Timestamp was inferred from the filename pattern rather than native EXIF.")
    elif record.timestamp_source.startswith("Filesystem"):
        score += 6
        reasons.append("Timestamp depends on filesystem metadata, which may change during copying or exporting.")

    if not record.has_gps:
        if source_type in {"Camera Photo", "Unknown"}:
            score += 7
            reasons.append("No GPS coordinates were available for a photo-like source.")
        else:
            reasons.append("GPS is unavailable, which is expected for screenshots or exported chat media.")
    else:
        confidence += 10
        reasons.append(f"GPS coordinates recovered: {record.gps_display}.")

    if record.software not in {"N/A", "", "Unknown"}:
        sw = record.software.lower()
        if any(term in sw for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            score += 18
            reasons.append(f"Software tag '{record.software}' suggests editing or export processing.")
        else:
            score += 4
            reasons.append(f"Software tag present: {record.software}.")

    if baseline_device and record.device_model not in {"Unknown", baseline_device}:
        score += 10
        reasons.append(f"Device differs from the dominant device observed in this batch ({baseline_device}).")

    if record.duplicate_group:
        score += 6
        confidence += 8
        reasons.append(f"Near-duplicate visual fingerprint match detected within {record.duplicate_group}.")

    if record.width and record.height:
        if min(record.width, record.height) < 720 and source_type == "Camera Photo":
            score += 6
            reasons.append("Unusually small dimensions for a camera-style image.")
        elif source_type in {"Screenshot", "Messaging Export", "Screenshot / Export"}:
            confidence += 5

    exif_dt = parse_timestamp(record.timestamp)
    if exif_dt:
        try:
            file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
            if abs((file_dt - exif_dt).days) > 365:
                score += 8
                reasons.append("Recovered time differs significantly from filesystem modified time.")
        except Exception:
            pass

    if source_type == "Edited / Exported":
        score += 10
        reasons.append("Source profile suggests edited/exported media rather than a direct camera original.")

    score = max(0, min(score, 100))
    confidence = max(0, min(confidence, 100))

    if score >= 60:
        level = "High"
    elif score >= 30:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No major metadata anomalies were detected.")

    return score, confidence, level, reasons
