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


def detect_anomalies(
    record: EvidenceRecord,
    baseline_device: str,
    file_path: Path,
) -> Tuple[int, int, str, List[str], int, int, int, List[str], List[str]]:
    authenticity = 0
    metadata = 0
    technical = 0
    confidence = 64
    reasons: List[str] = []
    breakdown: List[str] = []
    contributors: List[str] = []
    source_type = record.source_type

    def bump(bucket: str, points: int, reason: str, detail: str, contributor: str) -> None:
        nonlocal authenticity, metadata, technical
        if bucket == "authenticity":
            authenticity += points
        elif bucket == "metadata":
            metadata += points
        else:
            technical += points
        reasons.append(reason)
        breakdown.append(f"{bucket.title()} +{points} — {detail}")
        if contributor not in contributors:
            contributors.append(contributor)

    if record.parser_status == "Failed":
        confidence += 8
        bump(
            "technical",
            46,
            "Media decoder could not safely parse the file. Treat it as malformed, unsupported, or structurally damaged until validated.",
            "parser / decoder failure",
            "parser failure",
        )
    elif record.structure_status == "Animated":
        bump(
            "technical",
            6,
            "Animated media requires frame-aware review because the visible first frame may not represent the full artifact.",
            "animated media handling",
            "animated media",
        )
    elif record.structure_status == "Suspicious":
        bump(
            "technical",
            18,
            "The file structure is unusual for its extension or trust profile and should be validated before relying on it.",
            "unusual structure / trust mismatch",
            "suspicious structure",
        )

    if record.signature_status == "Mismatch":
        confidence += 6
        bump(
            "technical",
            24,
            "Extension and detected file signature do not align, which is a strong tamper or corruption indicator.",
            "extension vs signature mismatch",
            "signature mismatch",
        )
    elif record.format_trust in {"Weak", "Header-only"}:
        bump(
            "technical",
            8,
            "Container trust is limited because only partial header confidence was available for this file.",
            "limited container trust",
            "weak format trust",
        )

    if not record.exif:
        if source_type in {"Screenshot", "Messaging Export", "Screenshot / Export", "Graphic Asset"}:
            confidence += 10
            bump(
                "metadata",
                10,
                "Embedded metadata is limited, which is common for screenshots, exports, and graphic assets.",
                "limited native EXIF in export-like media",
                "thin metadata",
            )
        else:
            bump(
                "metadata",
                24,
                "No embedded EXIF metadata was recovered from the file.",
                "no embedded EXIF",
                "missing exif",
            )

    if record.timestamp == "Unknown":
        confidence -= 12
        bump(
            "authenticity",
            16,
            "Timestamp could not be recovered from EXIF, filename, or filesystem fallback.",
            "no recoverable time anchor",
            "missing timestamp",
        )
    elif record.timestamp_source == "Filename Pattern":
        confidence += 4
        bump(
            "authenticity",
            4,
            "Timestamp was inferred from the filename pattern rather than native EXIF.",
            "filename-based time anchor",
            "filename timestamp",
        )
    elif record.timestamp_source.startswith("Filesystem"):
        bump(
            "authenticity",
            8,
            "Timestamp depends on filesystem metadata, which may change during copying or export operations.",
            "filesystem-derived time anchor",
            "filesystem timestamp",
        )

    if not record.has_gps:
        if source_type in {"Camera Photo", "Unknown", "Edited / Exported"}:
            bump(
                "authenticity",
                7,
                "No GPS coordinates were available for a photo-like source.",
                "missing GPS for photo-like media",
                "missing gps",
            )
        else:
            reasons.append("GPS is unavailable, which is often normal for screenshots, graphics, and exported messaging media.")
    else:
        confidence += 10
        reasons.append(f"GPS coordinates recovered: {record.gps_display}.")
        if record.gps_confidence < 70 and "weak gps" not in contributors:
            contributors.append("weak gps")

    if record.software not in {"N/A", "", "Unknown"}:
        sw = record.software.lower()
        if any(term in sw for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            bump(
                "authenticity",
                18,
                f"Software tag '{record.software}' suggests editing or export processing.",
                "editor/export software tag",
                "editing software",
            )
        else:
            bump(
                "authenticity",
                4,
                f"Software tag present: {record.software}.",
                "software tag present",
                "software tag",
            )

    if record.hidden_code_indicators:
        confidence += 6
        bump(
            "technical",
            26,
            "Byte-level scanning recovered embedded code-like, credential-like, or script-capable content markers inside the container.",
            "embedded code/content markers",
            "hidden code markers",
        )
    elif record.extracted_strings:
        bump(
            "technical",
            4,
            "Readable embedded strings were recovered from the container even though no strong code markers were found.",
            "embedded string payloads",
            "embedded strings",
        )

    if baseline_device and record.device_model not in {"Unknown", baseline_device}:
        bump(
            "authenticity",
            10,
            f"Device differs from the dominant device observed in this batch ({baseline_device}).",
            "device continuity mismatch",
            "device mismatch",
        )

    if record.duplicate_group:
        confidence += 8
        bump(
            "authenticity",
            6,
            f"Near-duplicate visual fingerprint match detected within {record.duplicate_group}.",
            "duplicate cluster present",
            "duplicate cluster",
        )

    if record.width and record.height:
        if min(record.width, record.height) < 720 and source_type == "Camera Photo":
            bump(
                "authenticity",
                6,
                "Unusually small dimensions for a camera-style image.",
                "unusually small camera dimensions",
                "small camera dimensions",
            )
        elif source_type in {"Screenshot", "Messaging Export", "Screenshot / Export"}:
            confidence += 5
    else:
        bump(
            "technical",
            10,
            "Basic dimensions could not be read, which weakens trust in the parser output and preview pipeline.",
            "dimensions unavailable",
            "missing dimensions",
        )

    exif_dt = parse_timestamp(record.timestamp)
    if exif_dt:
        try:
            file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
            if abs((file_dt - exif_dt).days) > 365:
                bump(
                    "authenticity",
                    8,
                    "Recovered time differs significantly from filesystem modified time.",
                    "large EXIF/filesystem gap",
                    "timeline mismatch",
                )
        except Exception:
            pass

    if source_type == "Edited / Exported":
        bump(
            "authenticity",
            10,
            "Source profile suggests edited/exported media rather than a direct camera original.",
            "edited/exported profile",
            "edited workflow",
        )
    if source_type == "Malformed / Unsupported Asset":
        bump(
            "technical",
            18,
            "The file aligns with a malformed or unsupported asset profile and needs corroboration before content claims.",
            "malformed / unsupported asset profile",
            "malformed asset",
        )

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
    return score, confidence, level, reasons, authenticity, metadata, technical, breakdown, contributors
