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


def detect_anomalies(record: EvidenceRecord, baseline_device: str, file_path: Path) -> Tuple[int, int, str, List[str], int, int, int, List[str]]:
    authenticity = 0
    metadata = 0
    technical = 0
    confidence = 62
    reasons: List[str] = []
    breakdown: List[str] = []
    source_type = record.source_type

    if record.parser_status == "Failed":
        technical += 46
        confidence += 8
        reasons.append("Media decoder could not safely parse the file. Treat it as malformed, unsupported, or structurally damaged until validated.")
        breakdown.append("Technical +46 — parser / decoder failure")
    elif record.structure_status == "Animated":
        technical += 6
        reasons.append("Animated media requires frame-aware review because the visible first frame may not represent the full artifact.")
        breakdown.append("Technical +6 — animated media handling")
    elif record.structure_status == "Suspicious":
        technical += 18
        reasons.append("The file structure is unusual for its extension or trust profile and should be validated before relying on it.")
        breakdown.append("Technical +18 — unusual structure / trust mismatch")

    if record.signature_status == "Mismatch":
        technical += 24
        confidence += 6
        reasons.append("Extension and detected file signature do not align, which is a strong tamper or corruption indicator.")
        breakdown.append("Technical +24 — extension vs signature mismatch")
    elif record.format_trust in {"Weak", "Header-only"}:
        technical += 8
        reasons.append("Container trust is limited because only partial header confidence was available for this file.")
        breakdown.append("Technical +8 — limited container trust")

    if not record.exif:
        if source_type in {"Screenshot", "Messaging Export", "Screenshot / Export", "Graphic Asset"}:
            metadata += 10
            confidence += 10
            reasons.append("Embedded metadata is limited, which is common for screenshots, exports, and graphic assets.")
            breakdown.append("Metadata +10 — limited native EXIF in export-like media")
        else:
            metadata += 24
            reasons.append("No embedded EXIF metadata was recovered from the file.")
            breakdown.append("Metadata +24 — no embedded EXIF")

    if record.timestamp == "Unknown":
        authenticity += 16
        confidence -= 12
        reasons.append("Timestamp could not be recovered from EXIF, filename, or filesystem fallback.")
        breakdown.append("Authenticity +16 — no recoverable time anchor")
    elif record.timestamp_source == "Filename Pattern":
        authenticity += 4
        confidence += 4
        reasons.append("Timestamp was inferred from the filename pattern rather than native EXIF.")
        breakdown.append("Authenticity +4 — filename-based time anchor")
    elif record.timestamp_source.startswith("Filesystem"):
        authenticity += 8
        reasons.append("Timestamp depends on filesystem metadata, which may change during copying or export operations.")
        breakdown.append("Authenticity +8 — filesystem-derived time anchor")

    if not record.has_gps:
        if source_type in {"Camera Photo", "Unknown", "Edited / Exported"}:
            authenticity += 7
            reasons.append("No GPS coordinates were available for a photo-like source.")
            breakdown.append("Authenticity +7 — missing GPS for photo-like media")
        else:
            reasons.append("GPS is unavailable, which is often normal for screenshots, graphics, and exported messaging media.")
    else:
        confidence += 10
        reasons.append(f"GPS coordinates recovered: {record.gps_display}.")

    if record.software not in {"N/A", "", "Unknown"}:
        sw = record.software.lower()
        if any(term in sw for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            authenticity += 18
            reasons.append(f"Software tag '{record.software}' suggests editing or export processing.")
            breakdown.append("Authenticity +18 — editor/export software tag")
        else:
            authenticity += 4
            reasons.append(f"Software tag present: {record.software}.")
            breakdown.append("Authenticity +4 — software tag present")

    if baseline_device and record.device_model not in {"Unknown", baseline_device}:
        authenticity += 10
        reasons.append(f"Device differs from the dominant device observed in this batch ({baseline_device}).")
        breakdown.append("Authenticity +10 — device continuity mismatch")

    if record.duplicate_group:
        authenticity += 6
        confidence += 8
        reasons.append(f"Near-duplicate visual fingerprint match detected within {record.duplicate_group}.")
        breakdown.append("Authenticity +6 — duplicate cluster present")

    if record.width and record.height:
        if min(record.width, record.height) < 720 and source_type == "Camera Photo":
            authenticity += 6
            reasons.append("Unusually small dimensions for a camera-style image.")
            breakdown.append("Authenticity +6 — unusually small camera dimensions")
        elif source_type in {"Screenshot", "Messaging Export", "Screenshot / Export"}:
            confidence += 5
    else:
        technical += 10
        reasons.append("Basic dimensions could not be read, which weakens trust in the parser output and preview pipeline.")
        breakdown.append("Technical +10 — dimensions unavailable")

    exif_dt = parse_timestamp(record.timestamp)
    if exif_dt:
        try:
            file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
            if abs((file_dt - exif_dt).days) > 365:
                authenticity += 8
                reasons.append("Recovered time differs significantly from filesystem modified time.")
                breakdown.append("Authenticity +8 — large EXIF/filesystem gap")
        except Exception:
            pass

    if source_type == "Edited / Exported":
        authenticity += 10
        reasons.append("Source profile suggests edited/exported media rather than a direct camera original.")
        breakdown.append("Authenticity +10 — edited/exported profile")
    if source_type == "Malformed / Unsupported Asset":
        technical += 18
        breakdown.append("Technical +18 — malformed / unsupported asset profile")

    score = round(authenticity * 0.45 + metadata * 0.25 + technical * 0.65)
    score = max(0, min(score, 100))
    confidence = max(15, min(confidence, 98))

    if technical >= 44 or score >= 70:
        level = "High"
    elif score >= 35:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No major metadata anomalies were detected.")
    return score, confidence, level, reasons, authenticity, metadata, technical, breakdown
