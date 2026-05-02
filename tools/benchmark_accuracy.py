from __future__ import annotations

"""Small CLI helper for validation-dataset accuracy reporting.

Usage after analyzing evidence through the app:
  python tools/benchmark_accuracy.py path\to\records.json data\validation_ground_truth.sample.json
"""

import json
import sys
from pathlib import Path

from app.core.models import EvidenceRecord
from app.core.validation_accuracy import build_accuracy_report


def _records_from_json(path: Path) -> list[EvidenceRecord]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    rows = payload.get('records', payload) if isinstance(payload, dict) else payload
    out = []
    fields = set(EvidenceRecord.__dataclass_fields__)
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            try:
                out.append(EvidenceRecord(**{k: v for k, v in row.items() if k in fields}))
            except Exception:
                continue
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print('Usage: python tools/benchmark_accuracy.py records.json ground_truth.json')
        return 2
    records = _records_from_json(Path(argv[1]))
    report = build_accuracy_report(records, Path(argv[2]))
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
