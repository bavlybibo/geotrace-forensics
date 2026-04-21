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
        if record.perceptual_hash in {"", "Unavailable", "0" * 16}:
            continue
        buckets.setdefault(record.perceptual_hash, []).append(record)
    group_index = 1
    for phash, items in buckets.items():
        if len(items) > 1:
            group = f"Cluster-{group_index:02d}"
            for item in items:
                item.duplicate_group = group
            group_index += 1


def detect_anomalies(record: EvidenceRecord, baseline_device: str, file_path: Path) -> Tuple[int, int, str, List[str], int, int, int, List[str]]:
    authenticity = 0
    metadata = 0
    technical = 0
    confidence = 64
    reasons: List[str] = []
    breakdown: List[str] = []
    source_type = record.source_type

    if record.format_trust == "Mismatch":
        technical += 32
        confidence += 8
        reasons.append(f"The extension suggests {record.declared_format}, but the detected file signature indicates {record.detected_format}. Treat the file as mismatched until validated.")
        breakdown.append("Technical +32 — extension vs signature mismatch")

    if record.parser_status == "Failed":
        technical += 34
        confidence += 6
        reasons.append("Media decoding failed, so preview output and structural assumptions should be validated with a secondary parser.")
        breakdown.append("Technical +34 — parser / decoder failure")
    elif record.structure_status == "Animated":
        technical += 5
        reasons.append("Animated media needs frame-aware review because a single frame may not represent the full artifact.")
        breakdown.append("Technical +5 — animated media handling")
    elif record.structure_status in {"Suspicious", "Mismatch"}:
        technical += 14
        reasons.append("The file structure is unusual for its current trust profile and should be reviewed before relying on it.")
        breakdown.append("Technical +14 — unusual structure / trust state")

    if record.format_trust == "Weak":
        technical += 8
        reasons.append("The file header could not be strongly verified from the signature, so format trust remains weak.")
        breakdown.append("Technical +8 — weak format trust")

    if not record.exif:
        if source_type in {"Screenshot", "Messaging Export", "Screenshot / Export", "Graphic Asset"}:
            metadata += 8
            confidence += 8
            reasons.append("Embedded metadata is limited, which is common for screenshots, exports, and graphic assets.")
            breakdown.append("Metadata +8 — limited native EXIF in export-like media")
        else:
            metadata += 18
            reasons.append("No embedded EXIF metadata was recovered from the file.")
            breakdown.append("Metadata +18 — no embedded EXIF")

    if record.timestamp == "Unknown":
        authenticity += 14
        confidence -= 10
        reasons.append("No recoverable time anchor was found from EXIF, filename, or filesystem fallback.")
        breakdown.append("Authenticity +14 — no recoverable time anchor")
    elif record.timestamp_source == "Filename Pattern":
        authenticity += 4
        confidence += 4
        reasons.append("Timestamp was inferred from the filename pattern rather than native EXIF.")
        breakdown.append("Authenticity +4 — filename-based time anchor")
    elif record.timestamp_source.startswith("Filesystem"):
        authenticity += 7
        reasons.append("Timestamp depends on filesystem metadata, which can drift during copying or export operations.")
        breakdown.append("Authenticity +7 — filesystem-derived time anchor")

    if not record.has_gps:
        if source_type in {"Camera Photo", "Unknown", "Edited / Exported"}:
            authenticity += 6
            reasons.append("No GPS coordinates were available for a photo-like source.")
            breakdown.append("Authenticity +6 — missing GPS for photo-like media")
        else:
            reasons.append("GPS is unavailable, which is often normal for screenshots, graphics, and exported messaging media.")
    else:
        confidence += 10
        reasons.append(f"GPS coordinates recovered: {record.gps_display}.")

    if record.software not in {"N/A", "", "Unknown"}:
        sw = record.software.lower()
        if any(term in sw for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            authenticity += 14
            reasons.append(f"Software tag '{record.software}' suggests editing or export processing.")
            breakdown.append("Authenticity +14 — editor/export software tag")
        else:
            authenticity += 3
            reasons.append(f"Software tag present: {record.software}.")
            breakdown.append("Authenticity +3 — software tag present")

    if baseline_device and record.device_model not in {"Unknown", baseline_device}:
        authenticity += 8
        reasons.append(f"Device differs from the dominant device observed in this batch ({baseline_device}).")
        breakdown.append("Authenticity +8 — device continuity mismatch")

    if record.duplicate_group:
        authenticity += 5
        confidence += 6
        reasons.append(f"Near-duplicate visual fingerprint match detected within {record.duplicate_group}.")
        breakdown.append("Authenticity +5 — duplicate cluster present")

    if record.width and record.height:
        if min(record.width, record.height) < 720 and source_type == "Camera Photo":
            authenticity += 5
            reasons.append("Unusually small dimensions for a camera-style image.")
            breakdown.append("Authenticity +5 — unusually small camera dimensions")
        if record.brightness_mean <= 1.0:
            technical += 4
            reasons.append("The visible frame is nearly black or uniform, so content review should not rely on a quick glance alone.")
            breakdown.append("Technical +4 — near-uniform / near-black frame")
    else:
        technical += 8
        reasons.append("Basic dimensions could not be read, which weakens trust in the parser output and preview pipeline.")
        breakdown.append("Technical +8 — dimensions unavailable")

    exif_dt = parse_timestamp(record.timestamp)
    if exif_dt:
        try:
            file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
            if abs((file_dt - exif_dt).days) > 365:
                authenticity += 7
                reasons.append("Recovered time differs significantly from filesystem modified time.")
                breakdown.append("Authenticity +7 — large EXIF/filesystem gap")
        except Exception:
            pass

    if source_type == "Edited / Exported":
        authenticity += 9
        reasons.append("Source profile suggests edited or exported media rather than a direct camera original.")
        breakdown.append("Authenticity +9 — edited/exported profile")
    if source_type == "Malformed / Unsupported Asset":
        technical += 12
        breakdown.append("Technical +12 — malformed / unsupported asset profile")
    if source_type == "Signature Mismatch Asset":
        technical += 10
        breakdown.append("Technical +10 — signature mismatch source profile")

    score = round(authenticity * 0.42 + metadata * 0.22 + technical * 0.72)
    score = max(0, min(score, 100))
    confidence = max(18, min(confidence, 98))

    if technical >= 42 or score >= 68:
        level = "High"
    elif score >= 32:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No major metadata anomalies were detected.")
    return score, confidence, level, reasons, authenticity, metadata, technical, breakdown
