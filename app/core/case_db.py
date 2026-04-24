from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import CaseInfo, EvidenceRecord


class CaseDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    case_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_records (
                    case_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    file_name TEXT,
                    file_path TEXT,
                    sha256 TEXT,
                    md5 TEXT,
                    imported_at TEXT,
                    timestamp TEXT,
                    timestamp_source TEXT,
                    device_model TEXT,
                    gps_display TEXT,
                    suspicion_score INTEGER,
                    risk_level TEXT,
                    integrity_status TEXT,
                    note TEXT,
                    tags TEXT,
                    bookmarked INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (case_id, evidence_id),
                    FOREIGN KEY (case_id) REFERENCES cases(case_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS custody_log_case (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    action_time TEXT NOT NULL,
                    evidence_id TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    prev_hash TEXT,
                    event_hash TEXT,
                    FOREIGN KEY (case_id) REFERENCES cases(case_id)
                )
                """
            )
            self._ensure_column(connection, "custody_log_case", "prev_hash", "TEXT")
            self._ensure_column(connection, "custody_log_case", "event_hash", "TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_custody_case ON custody_log_case(case_id, id DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_records(case_id)")

    def create_case(self, case_id: str, case_name: str, *, set_active: bool = True) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with self._connect() as connection:
                if set_active:
                    connection.execute("UPDATE cases SET is_active = 0")
                connection.execute(
                    """
                    INSERT INTO cases(case_id, case_name, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (case_id, case_name, now, now, 1 if set_active else 0),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Case ID already exists and will not be overwritten: {case_id}") from exc

    def set_active_case(self, case_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE cases SET is_active = 0")
            connection.execute(
                "UPDATE cases SET is_active = 1, updated_at = ? WHERE case_id = ?",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), case_id),
            )

    def rename_case(self, case_id: str, case_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE cases SET case_name = ?, updated_at = ? WHERE case_id = ?",
                (case_name, datetime.now(timezone.utc).isoformat(timespec="seconds"), case_id),
            )

    def get_active_case(self) -> Optional[CaseInfo]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.case_id, c.case_name, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM evidence_records e WHERE e.case_id = c.case_id) AS item_count
                FROM cases c
                WHERE c.is_active = 1
                ORDER BY c.updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        return self._row_to_case(row) if row else None

    def list_cases(self) -> List[CaseInfo]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.case_id, c.case_name, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM evidence_records e WHERE e.case_id = c.case_id) AS item_count
                FROM cases c
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [self._row_to_case(row) for row in rows]

    def _row_to_case(self, row: sqlite3.Row) -> CaseInfo:
        return CaseInfo(
            case_id=row["case_id"],
            case_name=row["case_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            item_count=int(row["item_count"] or 0),
        )

    def upsert_evidence(self, record: EvidenceRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence_records(
                    case_id, evidence_id, file_name, file_path, sha256, md5, imported_at,
                    timestamp, timestamp_source, device_model, gps_display, suspicion_score,
                    risk_level, integrity_status, note, tags, bookmarked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id, evidence_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    file_path=excluded.file_path,
                    sha256=excluded.sha256,
                    md5=excluded.md5,
                    imported_at=excluded.imported_at,
                    timestamp=excluded.timestamp,
                    timestamp_source=excluded.timestamp_source,
                    device_model=excluded.device_model,
                    gps_display=excluded.gps_display,
                    suspicion_score=excluded.suspicion_score,
                    risk_level=excluded.risk_level,
                    integrity_status=excluded.integrity_status,
                    note=excluded.note,
                    tags=excluded.tags,
                    bookmarked=excluded.bookmarked
                """,
                (
                    record.case_id,
                    record.evidence_id,
                    record.file_name,
                    str(record.file_path),
                    record.sha256,
                    record.md5,
                    record.imported_at,
                    record.timestamp,
                    record.timestamp_source,
                    record.device_model,
                    record.gps_display,
                    record.suspicion_score,
                    record.risk_level,
                    record.integrity_status,
                    record.note,
                    record.tags,
                    1 if record.bookmarked else 0,
                ),
            )
            connection.execute(
                "UPDATE cases SET updated_at = ? WHERE case_id = ?",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), record.case_id),
            )

    def _latest_case_hash(self, connection: sqlite3.Connection, case_id: str) -> str:
        row = connection.execute(
            "SELECT event_hash FROM custody_log_case WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if row is None:
            return "GENESIS"
        return str(row["event_hash"] or "LEGACY")

    def _compute_event_hash(
        self,
        *,
        case_id: str,
        action_time: str,
        evidence_id: Optional[str],
        action: str,
        details: str,
        prev_hash: str,
    ) -> str:
        payload = "|".join([case_id, action_time, evidence_id or "CASE", action, details, prev_hash])
        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

    def log_action(self, case_id: str, evidence_id: Optional[str], action: str, details: str) -> None:
        normalized_action = (action or "UNKNOWN").strip().upper().replace(" ", "_")
        normalized_details = (details or "").strip() or "No details provided."
        action_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            prev_hash = self._latest_case_hash(connection, case_id)
            event_hash = self._compute_event_hash(
                case_id=case_id,
                action_time=action_time,
                evidence_id=evidence_id,
                action=normalized_action,
                details=normalized_details,
                prev_hash=prev_hash,
            )
            connection.execute(
                "INSERT INTO custody_log_case(case_id, action_time, evidence_id, action, details, prev_hash, event_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (case_id, action_time, evidence_id, normalized_action, normalized_details, prev_hash, event_hash),
            )
            connection.execute(
                "UPDATE cases SET updated_at = ? WHERE case_id = ?",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), case_id),
            )

    def fetch_logs(self, case_id: str):
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT action_time, evidence_id, action, details, prev_hash, event_hash FROM custody_log_case WHERE case_id = ? ORDER BY id DESC",
                    (case_id,),
                )
            )

    def fetch_logs_for_evidence(self, case_id: str, evidence_id: str):
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT action_time, evidence_id, action, details, prev_hash, event_hash FROM custody_log_case WHERE case_id = ? AND evidence_id = ? ORDER BY id DESC",
                    (case_id, evidence_id),
                )
            )

    def summarize_evidence_events(self, case_id: str, evidence_id: str, limit: int = 6) -> List[str]:
        rows = self.fetch_logs_for_evidence(case_id, evidence_id)
        return [
            f"{row['action_time']} • {row['action']} • {row['details']} • hash={str(row['event_hash'] or 'legacy')[:10]}"
            for row in rows[:limit]
        ]

    def verify_log_chain(self, case_id: str) -> tuple[bool, str]:
        with self._connect() as connection:
            rows = list(
                connection.execute(
                    "SELECT id, action_time, evidence_id, action, details, prev_hash, event_hash FROM custody_log_case WHERE case_id = ? ORDER BY id ASC",
                    (case_id,),
                )
            )
        if not rows:
            return True, "No custody activity logged yet."

        expected_prev = "GENESIS"
        for row in rows:
            prev_hash = str(row["prev_hash"] or "")
            event_hash = str(row["event_hash"] or "")
            if prev_hash != expected_prev:
                return False, f"Custody chain break detected before log row {row['id']}."
            expected_hash = self._compute_event_hash(
                case_id=case_id,
                action_time=row["action_time"],
                evidence_id=row["evidence_id"],
                action=row["action"],
                details=row["details"],
                prev_hash=prev_hash,
            )
            if event_hash != expected_hash:
                return False, f"Custody event hash mismatch detected at log row {row['id']}."
            expected_prev = event_hash
        return True, f"Custody chain verified across {len(rows)} event(s)."
