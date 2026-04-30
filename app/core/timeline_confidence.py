from __future__ import annotations

"""Small deterministic timeline confidence model.

The score is intentionally conservative: filename-derived or filesystem-only time is
a lead; native metadata and corroborated visible/app times score higher.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
import logging
from .structured_logging import log_failure

try:  # pragma: no cover
    from .models import EvidenceRecord
except Exception:  # pragma: no cover
    from app.core.models import EvidenceRecord


@dataclass(slots=True)
class TimelineConfidence:
    evidence_id: str
    score: int
    label: str
    source: str
    basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unique(values: Iterable[Any], limit: int = 6) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def build_timeline_confidence(record: EvidenceRecord, case_records: Iterable[EvidenceRecord] = ()) -> TimelineConfidence:
    base = max(0, min(100, int(getattr(record, "timestamp_confidence", 0) or 0)))
    source = str(getattr(record, "timestamp_source", "Unavailable") or "Unavailable")
    score = base
    basis: list[str] = []
    limitations: list[str] = []

    low_source = source.lower()
    if "exif" in low_source or "metadata" in low_source or "native" in low_source:
        score = max(score, min(95, base + 8))
        basis.append("native metadata time source")
    if "filename" in low_source:
        score = min(score or 58, 65)
        limitations.append("filename-derived timestamp; not a native capture-time proof")
    if "filesystem" in low_source or "modified" in low_source:
        score = min(max(score, 42), 70)
        limitations.append("filesystem times can change during copy/export workflows")
    if getattr(record, "visible_time_strings", []):
        score = max(score, min(88, base + 10))
        basis.append("visible/app time string recovered")
    if getattr(record, "time_conflicts", []):
        score = min(score, 55)
        limitations.extend(str(x) for x in getattr(record, "time_conflicts", [])[:3])

    peer_count = len([r for r in case_records if getattr(r, "timestamp", "Unknown") != "Unknown"])
    if peer_count >= 2:
        basis.append(f"case timeline contains {peer_count} anchored items")
    elif peer_count == 1:
        limitations.append("single-item timeline; ordering cannot be validated inside the case")

    if score >= 85:
        label = "strong timeline anchor"
    elif score >= 65:
        label = "usable timeline lead"
    elif score >= 35:
        label = "weak timeline lead"
    else:
        label = "no reliable timeline anchor"

    if not basis:
        basis.append(str(getattr(record, "timestamp_verdict", "No timestamp basis captured.")))
    return TimelineConfidence(
        evidence_id=str(getattr(record, "evidence_id", "")),
        score=max(0, min(100, int(score))),
        label=label,
        source=source,
        basis=_unique(basis, 6),
        limitations=_unique(limitations or ["corroborate with uploads, chats, cloud history, or source app logs"], 6),
        next_actions=["Do not make final chronology claims until this anchor is corroborated externally." if score < 85 else "Preserve the native file and manifest hashes with the timeline report."],
    )


def attach_timeline_confidence(record: EvidenceRecord, case_records: Iterable[EvidenceRecord] = ()) -> dict[str, Any]:
    payload = build_timeline_confidence(record, case_records).to_dict()
    try:
        setattr(record, "timeline_confidence_profile", payload)
    except Exception as exc:
        log_failure(
            logging.getLogger("geotrace"),
            context="timeline_confidence",
            operation="attach_timeline_confidence",
            evidence_id=str(getattr(record, "evidence_id", "")),
            message="Could not attach timeline confidence profile to the record object.",
            exc=exc,
            severity="warning",
            user_visible=False,
        )
    return payload
