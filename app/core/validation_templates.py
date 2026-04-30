from __future__ import annotations

"""Validation dataset helpers for measurable accuracy reports."""

import json
from pathlib import Path
from typing import Iterable

from .models import EvidenceRecord


def build_validation_ground_truth_template(records: Iterable[EvidenceRecord], dataset_name: str = "GeoTrace local validation set") -> dict:
    """Return a ground-truth JSON skeleton keyed by current file names.

    Analysts can fill the booleans/expected hints and save it as
    validation_ground_truth.json beside the evidence set.  The existing
    validation_service will then compute pass/fail metrics in exports.
    """
    payload: dict[str, object] = {
        "_dataset": dataset_name,
        "_instructions": [
            "Save this file as validation_ground_truth.json beside the evidence folder or original evidence files.",
            "Fill true/false values only when you know the expected ground truth.",
            "Leave unknown checks as null so they do not count as failures.",
        ],
    }
    for record in records:
        payload[record.file_name] = {
            "source_type_contains": record.source_type if record.source_type != "Unknown" else "",
            "source_type": "",
            "native_gps": None,
            "derived_geo": None,
            "hidden_payload": None,
            "parser_failure": None,
            "metadata_stripped": None,
            "duplicate_expected": None,
            "time_conflict": None,
            "software_contains": "",
            "duplicate_relation": "",
            "expected_note": "Fill analyst-known truth here.",
        }
    return payload


def write_validation_ground_truth_template(output_dir: Path, records: Iterable[EvidenceRecord], dataset_name: str = "GeoTrace local validation set") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "validation_ground_truth_template.json"
    path.write_text(json.dumps(build_validation_ground_truth_template(records, dataset_name), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
