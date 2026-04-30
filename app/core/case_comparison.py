from __future__ import annotations

"""Multi-case comparison helpers for enterprise/CTF investigations."""

from dataclasses import asdict, dataclass, field
from typing import Iterable, Any


@dataclass(slots=True)
class CaseComparisonResult:
    left_case: str
    right_case: str
    shared_sha256: list[str] = field(default_factory=list)
    shared_perceptual_hash: list[str] = field(default_factory=list)
    shared_device_models: list[str] = field(default_factory=list)
    shared_place_candidates: list[str] = field(default_factory=list)
    timeline_overlap: bool = False
    summary: str = "No comparison generated."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _set(records: Iterable[Any], attr: str, *, ignore: set[str] | None = None) -> set[str]:
    ignore = ignore or {"", "Unknown", "Unavailable", "N/A", "None"}
    return {str(getattr(record, attr, "") or "") for record in records if str(getattr(record, attr, "") or "") not in ignore}


def _places(records: Iterable[Any]) -> set[str]:
    out: set[str] = set()
    for record in records:
        for attr in ("candidate_city", "candidate_area", "possible_place", "location_estimate_label"):
            value = str(getattr(record, attr, "") or "")
            if value not in {"", "Unknown", "Unavailable", "N/A", "None"}:
                out.add(value)
        for value in getattr(record, "landmarks_detected", []) or []:
            if str(value).strip():
                out.add(str(value))
    return out


def compare_record_sets(left_records: Iterable[Any], right_records: Iterable[Any], *, left_case: str = "left", right_case: str = "right") -> CaseComparisonResult:
    left = list(left_records)
    right = list(right_records)
    shared_sha = sorted(_set(left, "sha256") & _set(right, "sha256"))
    shared_phash = sorted(_set(left, "perceptual_hash") & _set(right, "perceptual_hash"))
    shared_devices = sorted(_set(left, "device_model") & _set(right, "device_model"))
    shared_places = sorted(_places(left) & _places(right))
    left_times = _set(left, "timestamp")
    right_times = _set(right, "timestamp")
    overlap = bool(left_times & right_times)
    parts = []
    if shared_sha:
        parts.append(f"{len(shared_sha)} exact hash reuse hit(s)")
    if shared_phash:
        parts.append(f"{len(shared_phash)} visual/perceptual overlap hit(s)")
    if shared_places:
        parts.append(f"shared place lead(s): {', '.join(shared_places[:3])}")
    if shared_devices:
        parts.append(f"shared device model(s): {', '.join(shared_devices[:3])}")
    if overlap:
        parts.append("timeline anchor overlap detected")
    return CaseComparisonResult(
        left_case=left_case,
        right_case=right_case,
        shared_sha256=shared_sha[:12],
        shared_perceptual_hash=shared_phash[:12],
        shared_device_models=shared_devices[:12],
        shared_place_candidates=shared_places[:12],
        timeline_overlap=overlap,
        summary="; ".join(parts) if parts else "No strong cross-case relationship found.",
    )
