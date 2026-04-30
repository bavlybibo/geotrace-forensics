from __future__ import annotations

"""Validation dataset accuracy helpers."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Any
import json

try:  # pragma: no cover
    from .models import EvidenceRecord
except Exception:  # pragma: no cover
    from app.core.models import EvidenceRecord

@dataclass(slots=True)
class AccuracyReport:
    total_expected: int = 0
    matched: int = 0
    checks: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _load_ground_truth(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

def _actual_checks(record: EvidenceRecord) -> dict[str, Any]:
    has_native = bool(getattr(record, 'has_gps', False))
    derived = bool(getattr(record, 'derived_geo_confidence', 0) or getattr(record, 'derived_latitude', None) is not None or getattr(record, 'possible_geo_clues', []))
    map_detected = bool(getattr(record, 'map_intelligence_confidence', 0) or getattr(record, 'route_overlay_detected', False))
    hidden = bool(getattr(record, 'hidden_code_indicators', []) or getattr(record, 'hidden_suspicious_embeds', []) or getattr(record, 'pixel_hidden_score', 0))
    metrics = dict(getattr(record, 'image_detail_metrics', {}) or {})
    semantic = metrics.get('semantic_fingerprint') if isinstance(metrics.get('semantic_fingerprint'), dict) else {}
    local_vision = metrics.get('local_vision') if isinstance(metrics.get('local_vision'), dict) else {}
    return {
        'has_gps': has_native,
        'native_gps': has_native,
        'derived_geo': derived,
        'source_type': str(getattr(record, 'source_type', '')),
        'source_type_contains': str(getattr(record, 'source_type', '')),
        'map_detected': map_detected,
        'hidden_detected': hidden,
        'hidden_payload': hidden,
        'parser_failure': str(getattr(record, 'parser_status', 'Valid')) != 'Valid',
        'metadata_stripped': bool(getattr(record, 'metadata_issue_summary', '').lower().find('stripped') >= 0),
        'duplicate_expected': bool(getattr(record, 'duplicate_group', '')),
        'time_conflict': bool(getattr(record, 'time_conflicts', [])),
        'image_detail_generated': bool(getattr(record, 'image_detail_confidence', 0)),
        'semantic_fingerprint_generated': bool(semantic.get('fingerprint')),
        'local_vision_executed': bool(local_vision.get('executed')),
        'image_risk_is_dangerous': bool(getattr(record, 'image_risk_is_dangerous', False)),
        'image_risk_label': str(getattr(record, 'image_risk_label', 'SAFE')),
        'technical_threat': str((getattr(record, 'image_risk_verdict_payload', {}) or {}).get('technical_threat', 'Low')),
        'privacy_exposure': str((getattr(record, 'image_risk_verdict_payload', {}) or {}).get('privacy_exposure', 'Low')),
        'geo_sensitivity': str((getattr(record, 'image_risk_verdict_payload', {}) or {}).get('geo_sensitivity', 'Low')),
        'manipulation_suspicion': str((getattr(record, 'image_risk_verdict_payload', {}) or {}).get('manipulation_suspicion', 'Low')),
        'map_route_detected': bool(getattr(record, 'route_overlay_detected', False)),
        'ocr_confidence_min': int(getattr(record, 'ocr_confidence', 0) or 0),
        'software_contains': str(getattr(record, 'software', '')),
        'duplicate_relation': str(getattr(record, 'duplicate_relation', '')),
    }

def _matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return bool(actual) == expected
    if isinstance(expected, (int, float)):
        return actual == expected
    return str(expected).lower() in str(actual).lower()

def build_accuracy_report(records: Iterable[EvidenceRecord], ground_truth_path: Path | str) -> AccuracyReport:
    truth = _load_ground_truth(Path(ground_truth_path))
    truth = {k: v for k, v in truth.items() if not str(k).startswith('_')}
    by_name = {str(getattr(r, 'file_name', '')): r for r in records}
    report = AccuracyReport(total_expected=len(truth))
    for file_name, expected in truth.items():
        if not isinstance(expected, dict):
            continue
        record = by_name.get(str(file_name))
        if record is None:
            report.details.append(f'MISS {file_name}: no analyzed record')
            continue
        report.matched += 1
        checks = _actual_checks(record)
        for key, expected_value in expected.items():
            if key in {'expected_note'} or expected_value is None or expected_value == '':
                report.skipped += 1
                continue
            if key not in checks:
                report.skipped += 1
                report.details.append(f'SKIP {file_name}.{key}: unsupported validation key')
                continue
            report.checks += 1
            actual = checks[key]
            if str(key).endswith('_min') and isinstance(expected_value, (int, float)):
                matched = float(actual or 0) >= float(expected_value)
            else:
                matched = _matches(actual, expected_value)
            if matched:
                report.passed += 1
                report.details.append(f'PASS {file_name}.{key}: {actual}')
            else:
                report.failed += 1
                report.details.append(f'FAIL {file_name}.{key}: expected {expected_value}, got {actual}')
    report.pass_rate = round((report.passed / report.checks) * 100, 2) if report.checks else 0.0
    return report
