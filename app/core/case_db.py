from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import EvidenceRecord


class CaseDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    file_name TEXT,
                    file_path TEXT,
                    sha256 TEXT,
                    md5 TEXT,
                    imported_at TEXT,
                    timestamp TEXT,
                    device_model TEXT,
                    gps_display TEXT,
                    suspicion_score INTEGER,
                    risk_level TEXT,
                    integrity_status TEXT,
                    note TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS custody_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_time TEXT,
                    evidence_id TEXT,
                    action TEXT,
                    details TEXT
                )
                """
            )

    def reset_case(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM evidence")
            connection.execute("DELETE FROM custody_log")
            connection.commit()

    def upsert_evidence(self, record: EvidenceRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence(
                    evidence_id, file_name, file_path, sha256, md5, imported_at,
                    timestamp, device_model, gps_display, suspicion_score,
                    risk_level, integrity_status, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    file_path=excluded.file_path,
                    sha256=excluded.sha256,
                    md5=excluded.md5,
                    imported_at=excluded.imported_at,
                    timestamp=excluded.timestamp,
                    device_model=excluded.device_model,
                    gps_display=excluded.gps_display,
                    suspicion_score=excluded.suspicion_score,
                    risk_level=excluded.risk_level,
                    integrity_status=excluded.integrity_status,
                    note=excluded.note
                """,
                (
                    record.evidence_id,
                    record.file_name,
                    str(record.file_path),
                    record.sha256,
                    record.md5,
                    record.imported_at,
                    record.timestamp,
                    record.device_model,
                    record.gps_display,
                    record.suspicion_score,
                    record.risk_level,
                    record.integrity_status,
                    record.note,
                ),
            )

    def log_action(self, evidence_id: str, action: str, details: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO custody_log(action_time, evidence_id, action, details) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(timespec="seconds"), evidence_id, action, details),
            )

    def fetch_logs(self):
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT action_time, evidence_id, action, details FROM custody_log ORDER BY id DESC"
                )
            )
