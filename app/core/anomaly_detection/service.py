"""Duplicate, timeline, scene, and anomaly detection implementation.

Moved from app.core.anomalies during v12.10.2 organization-only refactor.
"""

from __future__ import annotations

from collections import Counter
import logging
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable, List, Tuple

from ..models import EvidenceRecord


LOGGER = logging.getLogger("geotrace.anomalies")

DATE_FORMATS = ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]


def parse_timestamp(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except Exception as exc:
            LOGGER.debug("Timestamp %r did not match format %s: %s", value, fmt, exc)
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
    except Exception as exc:
        LOGGER.debug("Invalid pHash values left=%r right=%r: %s", left, right, exc)
        return 64


def _record_tokens(record: EvidenceRecord) -> set[str]:
    tokens: set[str] = set()
    for bucket in [record.ocr_map_labels, record.ocr_location_entities, record.ocr_username_entities, record.visible_urls, record.visible_text_lines[:4]]:
        for item in bucket:
            for token in re.findall(r"[A-Za-z0-9_@.-]{3,}", item.lower()):
                if token.startswith("http"):
                    continue
                tokens.add(token)
    return tokens


def _name_duplicate_hint(record: EvidenceRecord) -> bool:
    name = f"{record.file_name} {record.evidence_id}".lower()
    return any(token in name for token in ["duplicate", "dupe", "copy", "stripped", "clone"])


def _source_family(record: EvidenceRecord) -> str:
    source = f"{record.source_type} {record.source_subtype}".lower()
    if "camera" in source:
        return "camera"
    if any(token in source for token in ["screenshot", "export", "messaging", "chat", "browser", "desktop", "mobile"]):
        return "screen"
    if any(token in source for token in ["asset", "graphic", "malformed"]):
        return "asset"
    return "other"


def _relation_details(left: EvidenceRecord, right: EvidenceRecord, *, max_distance: int) -> tuple[str, int, int, str] | None:
    if left.sha256 and right.sha256 and left.sha256 == right.sha256:
        return "Exact duplicate", 100, 0, "sha256"

    distance = _phash_distance(left.perceptual_hash, right.perceptual_hash)
    same_dimensions = bool(left.width and right.width and left.width == right.width and left.height == right.height)
    size_ratio = 0.0
    if left.file_size and right.file_size:
        size_ratio = min(left.file_size, right.file_size) / max(left.file_size, right.file_size)
    token_overlap = len(_record_tokens(left) & _record_tokens(right))

    # pHash alone is not enough for forensic duplicate grouping: simple scenes,
    # map screenshots, or low-detail assets can collide. Promote a relation only
    # when the visual fingerprint is supported by a provenance/name/text signal.
    left_family = _source_family(left)
    right_family = _source_family(right)
    if {left_family, right_family} == {"camera", "screen"}:
        return None
    if "asset" in {left_family, right_family} and not (_name_duplicate_hint(left) or _name_duplicate_hint(right)):
        return None

    name_hint = _name_duplicate_hint(left) or _name_duplicate_hint(right)
    text_match = token_overlap >= 2
    name_supported_match = name_hint and distance <= max_distance and (same_dimensions or (left_family == right_family and distance <= 2))
    size_supported_match = (
        distance <= 1
        and size_ratio >= 0.95
        and left_family == right_family
        and left_family not in {"asset"}
    )

    if distance <= max_distance and (text_match or name_supported_match or size_supported_match):
        score = max(72, min(99, 100 - (distance * 7)))
        method_bits = ["phash"]
        if same_dimensions:
            method_bits.append("dimensions")
        if size_ratio >= 0.25 or size_supported_match:
            method_bits.append("size")
        if token_overlap >= 2:
            method_bits.append("text overlap")
        if name_hint:
            method_bits.append("filename hint")
        return "Near duplicate", score, distance, " + ".join(method_bits)

    if distance <= max_distance + 4 and (text_match or (name_hint and same_dimensions)):
        score = max(48, min(86, 90 - (distance * 4)))
        method_bits = ["phash"]
        if same_dimensions:
            method_bits.append("dimensions")
        if size_ratio >= 0.40:
            method_bits.append("size")
        if token_overlap >= 2:
            method_bits.append("text overlap")
        if name_hint:
            method_bits.append("filename hint")
        return "Derivative / related", score, distance, " + ".join(method_bits)

    return None


def assign_duplicate_groups(records: List[EvidenceRecord], *, max_distance: int = 6) -> None:
    for record in records:
        record.duplicate_group = ""
        record.duplicate_relation = ""
        record.duplicate_method = ""
        record.duplicate_peers = []
        record.duplicate_distance = 0
        record.similarity_score = 0
        record.similarity_note = "No near-duplicate peer was identified."

    relations: dict[tuple[int, int], tuple[str, int, int, str]] = {}
    adjacency: dict[int, set[int]] = {idx: set() for idx in range(len(records))}
    for left_idx in range(len(records)):
        for right_idx in range(left_idx + 1, len(records)):
            relation = _relation_details(records[left_idx], records[right_idx], max_distance=max_distance)
            if relation is None:
                continue
            relations[(left_idx, right_idx)] = relation
            adjacency[left_idx].add(right_idx)
            adjacency[right_idx].add(left_idx)

    group_index = 1
    visited: set[int] = set()
    for start in range(len(records)):
        if start in visited or not adjacency[start]:
            continue
        stack = [start]
        cluster: list[int] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            cluster.append(current)
            stack.extend(sorted(adjacency[current] - visited))
        if len(cluster) <= 1:
            continue
        label = f"Cluster-{group_index:02d}"
        group_index += 1
        for idx in cluster:
            record = records[idx]
            peers = [peer for peer in cluster if peer != idx]
            peer_details = []
            for peer in peers:
                pair = (min(idx, peer), max(idx, peer))
                detail = relations.get(pair)
                if detail is None:
                    continue
                peer_details.append((peer, detail))
            if not peer_details:
                continue
            peer_details.sort(key=lambda item: (-item[1][1], item[1][2], records[item[0]].evidence_id))
            best_peer, best = peer_details[0]
            relation_type, score, distance, method = best
            record.duplicate_group = label
            record.duplicate_relation = relation_type
            record.duplicate_method = method
            record.duplicate_distance = distance
            record.duplicate_peers = [records[peer].evidence_id for peer, _ in peer_details[:4]]
            record.similarity_score = score
            if relation_type == "Exact duplicate":
                record.similarity_note = f"Exact duplicate linkage in {label} via identical SHA-256 hash."
            elif relation_type == "Near duplicate":
                record.similarity_note = f"Near-duplicate similarity score {score}% within {label} (distance {distance}, method {method})."
            else:
                record.similarity_note = f"Derivative/related match {score}% within {label} (distance {distance}, method {method})."

    for idx, record in enumerate(records):
        if record.duplicate_group:
            continue
        peer_details = []
        for other_idx in range(len(records)):
            if other_idx == idx:
                continue
            relation = _relation_details(record, records[other_idx], max_distance=max_distance)
            if relation is not None:
                peer_details.append((other_idx, relation))
        if peer_details:
            peer_details.sort(key=lambda item: (-item[1][1], item[1][2], records[item[0]].evidence_id))
            best_peer, best = peer_details[0]
            relation_type, score, distance, method = best
            record.similarity_score = score
            record.duplicate_distance = distance
            record.duplicate_relation = relation_type
            record.duplicate_method = method
            record.duplicate_peers = [records[best_peer].evidence_id]
            record.similarity_note = f"Closest visual peer is {records[best_peer].evidence_id}: {relation_type.lower()} ({score}%, method {method})."


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

    if getattr(record, "pixel_hidden_score", 0) >= 40 or getattr(record, "pixel_lsb_strings", []):
        confidence += 4
        bump(
            "technical",
            18 if getattr(record, "pixel_hidden_score", 0) >= 70 else 10,
            getattr(record, "pixel_hidden_summary", "Pixel-level hidden-content anomaly detected."),
            "pixel-level hidden-content heuristic",
            "pixel stego lead",
        )

    image_quality_flags = list(getattr(record, "image_quality_flags", []) or [])
    if image_quality_flags and any("alpha" in flag.lower() or "hidden" in flag.lower() or "very dark" in flag.lower() for flag in image_quality_flags):
        confidence += 2
        reasons.append("Image-detail intelligence flagged visual conditions that may affect OCR, hidden-content review, or analyst interpretation: " + "; ".join(image_quality_flags[:2]) + ".")
        contributors.append("image detail quality flags")

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
        except Exception as exc:
            LOGGER.debug("Non-critical anomaly branch failed: %s", exc)

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
        breakdown.append("Status +0 — no major metadata anomaly was converted into an issue.")
    return score, confidence, level, reasons, authenticity, metadata, technical, breakdown, contributors
