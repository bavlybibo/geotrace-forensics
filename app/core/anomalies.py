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


def _phash_distance(left: str, right: str) -> int:
    try:
        if len(left) != len(right) or not left or left == "0" * len(left) or right == "0" * len(right):
            return 64
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except Exception:
        return 64


def assign_duplicate_groups(records: List[EvidenceRecord], *, max_distance: int = 6) -> None:
    valid_indices = [
        idx for idx, record in enumerate(records)
        if record.perceptual_hash and record.perceptual_hash != "0" * len(record.perceptual_hash)
    ]
    for record in records:
        record.duplicate_group = ""
        record.similarity_score = 0
        record.similarity_note = "No near-duplicate peer was identified."
    group_index = 1
    visited: set[int] = set()
    for start in valid_indices:
        if start in visited:
            continue
        cluster = {start}
        queue = [start]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            current_hash = records[current].perceptual_hash
            for peer in valid_indices:
                if peer == current or peer in cluster:
                    continue
                if _phash_distance(current_hash, records[peer].perceptual_hash) <= max_distance:
                    cluster.add(peer)
                    queue.append(peer)
        if len(cluster) > 1:
            group = f"Cluster-{group_index:02d}"
            members = sorted(cluster)
            for idx in members:
                record = records[idx]
                distances = [_phash_distance(record.perceptual_hash, records[peer].perceptual_hash) for peer in members if peer != idx]
                best_distance = min(distances) if distances else 0
                record.duplicate_group = group
                record.similarity_score = max(42, min(99, 100 - (best_distance * 8)))
                record.similarity_note = f"Near-duplicate similarity score {record.similarity_score}% within {group}."
            group_index += 1
    for idx in valid_indices:
        if records[idx].duplicate_group:
            continue
        distances = []
        for peer in valid_indices:
            if peer == idx:
                continue
            dist = _phash_distance(records[idx].perceptual_hash, records[peer].perceptual_hash)
            if dist < 64:
                distances.append(dist)
        if distances:
            best_distance = min(distances)
            records[idx].similarity_score = max(0, 100 - (best_distance * 8))
            records[idx].similarity_note = f"Closest visual peer distance {best_distance} (approx. {records[idx].similarity_score}% similarity)."


def assign_scene_groups(records: List[EvidenceRecord], *, hours_window: int = 6) -> None:
    for record in records:
        record.scene_group = ""
    ordered = sorted(records, key=lambda r: (parse_timestamp(r.timestamp) is None, parse_timestamp(r.timestamp) or datetime.max, r.evidence_id))
    groups: List[List[EvidenceRecord]] = []
    for record in ordered:
        dt = parse_timestamp(record.timestamp)
        placed = False
        for group in groups:
            anchor = group[0]
            anchor_dt = parse_timestamp(anchor.timestamp)
            if dt is None or anchor_dt is None:
                continue
            same_source = record.source_type == anchor.source_type or (record.app_detected != "Unknown" and record.app_detected == anchor.app_detected)
            within_window = abs((dt - anchor_dt).total_seconds()) <= hours_window * 3600
            same_duplicate = record.duplicate_group and record.duplicate_group == anchor.duplicate_group
            if same_duplicate or (same_source and within_window):
                group.append(record)
                placed = True
                break
        if not placed:
            groups.append([record])
    scene_index = 1
    for group in groups:
        if len(group) <= 1:
            continue
        label = f"Scene-{scene_index:02d}"
        for record in group:
            record.scene_group = label
        scene_index += 1


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
    elif record.hidden_suspicious_embeds:
        bump(
            "technical",
            14,
            "Tiered hidden-content scanning found structural warnings such as trailing bytes, encoded blobs, or appended payload hints.",
            "hidden-content structural warning",
            "hidden-content structural warning",
        )
    elif record.extracted_strings:
        reasons.append(
            "Readable embedded strings were recovered from the container, but no strong code markers were found. Treat them as analyst context only unless another parser confirms payload intent."
        )
        breakdown.append("Technical +0 — readable strings retained for context only")

    if record.derived_geo_display != "Unavailable" and not record.has_gps:
        reasons.append(
            f"No native GPS was recovered, but visible content exposed a screenshot-derived location clue at {record.derived_geo_display}."
        )
        breakdown.append("Metadata +0 — derived geolocation clue retained separately from native GPS")

    if record.time_conflicts:
        bump(
            "authenticity",
            9,
            "Different time candidates disagree materially, so chronology should remain conservative until corroborated externally.",
            "time-candidate conflict",
            "time conflict",
        )

    if record.visible_urls and source_type == "Camera Photo":
        bump(
            "authenticity",
            12,
            "Visible browser or URL clues do not fit a clean camera-original profile.",
            "camera-photo vs browser-content mismatch",
            "workflow mismatch",
        )

    if source_type in {"Map Screenshot", "Browser Screenshot"}:
        reasons.append("On-screen OCR clues indicate a browser or map workflow, so visible text, URLs, and screenshot context should be preserved.")
        confidence += 5

    if record.environment_profile.startswith("Desktop") and record.width and record.height and record.width < record.height and "Screenshot" in source_type:
        bump(
            "authenticity",
            5,
            "Desktop-screenshot label conflicts slightly with the current aspect ratio and should be double-checked.",
            "environment/aspect mismatch",
            "environment mismatch",
        )

    if record.stego_suspicion and "No strong" not in record.stego_suspicion:
        bump(
            "technical",
            11,
            record.stego_suspicion,
            "stego / appended-payload heuristic",
            "stego suspicion",
        )

    if record.scene_group:
        reasons.append(f"Scene grouping linked this file to {record.scene_group}, which helps collapse related screenshots or derivative media into one investigative sequence.")

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
