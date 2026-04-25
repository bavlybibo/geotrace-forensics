from __future__ import annotations

"""Structured OSINT data contracts used by the deterministic analysis layer.

These models are deliberately simple and serialisable. GeoTrace treats OSINT output as
analyst leads unless it is corroborated by native metadata, verified source-app data,
or another trusted source. The CTF/GeoLocator models live here intentionally so the
CTF workflow remains part of OSINT rather than a separate, conflicting subsystem.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class OSINTEntity:
    """A sensitive pivot recovered from visible/OCR/contextual evidence."""

    value: str
    entity_type: str
    source: str = "unknown"
    confidence: int = 0
    sensitivity: str = "internal"
    note: str = "Use only within the authorised investigation scope."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OSINTHypothesis:
    """A structured, courtroom-safe OSINT hypothesis.

    `strength` should stay conservative: proof > lead > weak_signal > no_signal.
    """

    title: str
    claim: str
    strength: str = "weak_signal"
    confidence: int = 0
    basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    source: str = "deterministic-osint"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CorroborationItem:
    claim: str
    status: str = "needs_corroboration"
    supporting_basis: list[str] = field(default_factory=list)
    missing_basis: list[str] = field(default_factory=list)
    recommended_action: str = "Corroborate this lead before reporting it as fact."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CTFClue:
    """A CTF/GeoGuessr-style clue extracted from the evidence item.

    The clue is intentionally source-labelled so filename-only hints cannot be confused
    with OCR, GPS, visual, or map evidence.
    """

    clue_type: str  # text / visual / map / metadata / filename / country / landmark
    value: str
    source: str = "unknown"
    confidence: int = 0
    evidence_strength: str = "weak_signal"
    why_it_matters: str = "May help narrow the image location during authorised OSINT review."
    privacy_note: str = "Do not run external searches unless authorised and privacy-reviewed."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GeoCandidate:
    """A ranked location candidate for OSINT/CTF geolocation work."""

    level: str  # country / city / area / poi / coordinates / filename_hint
    name: str
    confidence: int = 0
    evidence_strength: str = "weak_signal"
    basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    status: str = "needs_review"  # needs_review / verified / rejected
    analyst_note: str = ""
    analyst_updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CTFGeoProfile:
    """OSINT-owned CTF geolocation bundle for a single evidence record."""

    clues: list[CTFClue] = field(default_factory=list)
    candidates: list[GeoCandidate] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    solvability_score: int = 0
    solvability_label: str = "No useful geo clue"
    country_region_profile: str = "Unknown"
    landmark_matches: list[dict[str, Any]] = field(default_factory=list)
    writeup: str = "CTF geolocation writeup has not been generated yet."
    online_mode_status: str = "Offline-only. External/reverse-image searches require explicit analyst action and privacy review."
    image_existence_profile: dict[str, Any] = field(default_factory=dict)
    online_privacy_review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clues": [item.to_dict() for item in self.clues],
            "candidates": [item.to_dict() for item in self.candidates],
            "search_queries": list(self.search_queries),
            "solvability_score": int(self.solvability_score or 0),
            "solvability_label": self.solvability_label,
            "country_region_profile": self.country_region_profile,
            "landmark_matches": list(self.landmark_matches),
            "writeup": self.writeup,
            "online_mode_status": self.online_mode_status,
            "image_existence_profile": dict(self.image_existence_profile),
            "online_privacy_review": dict(self.online_privacy_review),
        }


@dataclass(slots=True)
class OSINTSignalProfile:
    entities: list[OSINTEntity] = field(default_factory=list)
    hypotheses: list[OSINTHypothesis] = field(default_factory=list)
    corroboration_matrix: list[CorroborationItem] = field(default_factory=list)
    ctf_profile: CTFGeoProfile = field(default_factory=CTFGeoProfile)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [item.to_dict() for item in self.entities],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "corroboration_matrix": [item.to_dict() for item in self.corroboration_matrix],
            "ctf_profile": self.ctf_profile.to_dict(),
        }
