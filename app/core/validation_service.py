from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import EvidenceRecord


def _candidate_truth_paths(records: Iterable[EvidenceRecord]) -> List[Path]:
    paths: List[Path] = []
    seen = set()
    for record in records:
        for base in [record.original_file_path.parent, record.file_path.parent, record.original_file_path.parent.parent]:
            candidate = base / "validation_ground_truth.json"
            if candidate.exists() and candidate not in seen:
                seen.add(candidate)
                paths.append(candidate)
    return paths


def load_ground_truth(records: Iterable[EvidenceRecord]) -> Dict[str, dict]:
    for path in _candidate_truth_paths(records):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _truth_bool(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    return None


def evaluate_record(record: EvidenceRecord, expected: dict) -> tuple[List[str], List[str]]:
    hits: List[str] = []
    misses: List[str] = []

    def check(label: str, actual: bool, expected_value: Optional[bool]) -> None:
        if expected_value is None:
            return
        if actual == expected_value:
            hits.append(label)
        else:
            misses.append(f"{label} expected {expected_value} got {actual}")

    contains = expected.get("source_type_contains")
    if contains:
        if str(contains).lower() in record.source_type.lower() or str(contains).lower() in record.source_subtype.lower():
            hits.append("source type")
        else:
            misses.append(f"source type expected to include '{contains}' but got '{record.source_type}/{record.source_subtype}'")

    exact_source = expected.get("source_type")
    if exact_source:
        if record.source_type == exact_source:
            hits.append("exact source type")
        else:
            misses.append(f"source type expected '{exact_source}' got '{record.source_type}'")

    check("native GPS", record.has_gps, _truth_bool(expected.get("native_gps")))
    check("derived geo", record.derived_geo_display != "Unavailable" or bool(record.possible_geo_clues), _truth_bool(expected.get("derived_geo")))
    check("hidden payload", bool(record.hidden_code_indicators or record.hidden_suspicious_embeds), _truth_bool(expected.get("hidden_payload")))
    check("parser failure", record.parser_status != "Valid", _truth_bool(expected.get("parser_failure")))
    check("metadata stripped", not bool(record.exif), _truth_bool(expected.get("metadata_stripped")))
    check("duplicate grouping", bool(record.duplicate_group), _truth_bool(expected.get("duplicate_expected")))
    check("time conflict", bool(record.time_conflicts), _truth_bool(expected.get("time_conflict")))
    metrics = dict(getattr(record, "image_detail_metrics", {}) or {})
    semantic = metrics.get("semantic_fingerprint") if isinstance(metrics.get("semantic_fingerprint"), dict) else {}
    local_vision = metrics.get("local_vision") if isinstance(metrics.get("local_vision"), dict) else {}
    check("image detail generated", bool(getattr(record, "image_detail_confidence", 0)), _truth_bool(expected.get("image_detail_generated")))
    check("semantic fingerprint", bool(semantic.get("fingerprint")), _truth_bool(expected.get("semantic_fingerprint_generated")))
    check("local vision executed", bool(local_vision.get("executed")), _truth_bool(expected.get("local_vision_executed")))
    check("map route detected", bool(getattr(record, "route_overlay_detected", False)), _truth_bool(expected.get("map_route_detected")))
    if expected.get("ocr_confidence_min") is not None:
        try:
            threshold = int(expected.get("ocr_confidence_min"))
            if int(getattr(record, "ocr_confidence", 0) or 0) >= threshold:
                hits.append("ocr confidence minimum")
            else:
                misses.append(f"ocr confidence expected >= {threshold} got {getattr(record, 'ocr_confidence', 0)}")
        except Exception:
            misses.append("ocr confidence minimum expected value is invalid")

    if expected.get("software_contains"):
        term = str(expected["software_contains"]).lower()
        if term in (record.software or "").lower():
            hits.append("software tag")
        else:
            misses.append(f"software tag expected to include '{term}' but got '{record.software}'")

    if expected.get("duplicate_relation"):
        term = str(expected["duplicate_relation"]).lower()
        if term in (record.duplicate_relation or "").lower():
            hits.append("duplicate relation")
        else:
            misses.append(f"duplicate relation expected '{term}' but got '{record.duplicate_relation}'")

    return hits, misses


def build_validation_metrics(records: List[EvidenceRecord]) -> Dict[str, object]:
    truth = load_ground_truth(records)
    metrics: Dict[str, object] = {
        "ground_truth_loaded": bool(truth),
        "dataset_name": truth.get("_dataset", "No linked validation dataset"),
        "record_count": len(records),
        "evaluated_records": 0,
        "assertions": 0,
        "passes": 0,
        "failures": 0,
        "per_record": {},
        "summary": "No linked validation dataset was found for the current evidence set.",
    }
    if not truth:
        for record in records:
            record.validation_hits = []
            record.validation_misses = []
        return metrics

    for record in records:
        expected = truth.get(record.file_name)
        if not isinstance(expected, dict):
            record.validation_hits = []
            record.validation_misses = []
            continue
        hits, misses = evaluate_record(record, expected)
        record.validation_hits = hits
        record.validation_misses = misses
        metrics["evaluated_records"] = int(metrics["evaluated_records"]) + 1
        metrics["assertions"] = int(metrics["assertions"]) + len(hits) + len(misses)
        metrics["passes"] = int(metrics["passes"]) + len(hits)
        metrics["failures"] = int(metrics["failures"]) + len(misses)
        metrics["per_record"][record.file_name] = {"hits": hits, "misses": misses}

    assertions = int(metrics["assertions"])
    passes = int(metrics["passes"])
    coverage = int(metrics["evaluated_records"])
    if assertions:
        pass_rate = round((passes / assertions) * 100, 1)
        metrics["pass_rate"] = pass_rate
        metrics["summary"] = (
            f"Validation dataset '{metrics['dataset_name']}' covered {coverage}/{len(records)} file(s). "
            f"Assertions passed: {passes}/{assertions} ({pass_rate}%)."
        )
    else:
        metrics["pass_rate"] = 0.0
        metrics["summary"] = f"Validation dataset '{metrics['dataset_name']}' was found, but no assertions matched the current file names."
    return metrics
