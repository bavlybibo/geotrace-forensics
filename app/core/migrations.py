from __future__ import annotations

"""Explicit migration ledger for case-store compatibility.

The SQLite layer still performs its additive column checks internally. This module
keeps a human-readable, versioned ledger next to case data so release packages can
prove which migration contracts were considered when a case was opened.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LOGGER = logging.getLogger("geotrace.migrations")
CURRENT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    description: str
    runner: Callable[[Path, Path], None]


def _noop(_project_root: Path, _case_root: Path) -> None:
    return None


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="001_baseline_case_db_snapshot_contract",
        description="Record baseline case DB + snapshot compatibility contract.",
        runner=_noop,
    ),
    Migration(
        version=2,
        name="002_structured_osint_cache_contract",
        description="Record structured OSINT cache/snapshot fields used by v12.8.14+.",
        runner=_noop,
    ),
)


def _read_existing_ledger(ledger_path: Path) -> dict:
    if not ledger_path.exists():
        return {}
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        LOGGER.warning("Could not read migration ledger %s: %s", ledger_path, exc)
        return {}


def run_migrations(project_root: Path, case_root: Path) -> dict:
    ledger_path = case_root / "schema_version.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    old = _read_existing_ledger(ledger_path)
    try:
        previous = int(old.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        previous = 0

    applied: list[dict] = []
    for migration in MIGRATIONS:
        if previous < migration.version:
            migration.runner(project_root, case_root)
            applied.append(asdict(migration) | {"runner": migration.runner.__name__})

    ledger = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "previous_schema_version": previous,
        "applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applied_migrations": applied,
        "available_migrations": [
            {"version": m.version, "name": m.name, "description": m.description} for m in MIGRATIONS
        ],
        "note": "CaseDatabase performs additive column checks; this ledger records explicit release migration contracts.",
    }
    tmp = ledger_path.with_suffix(ledger_path.suffix + ".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ledger_path)
    return ledger
