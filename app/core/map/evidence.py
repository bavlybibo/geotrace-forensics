from __future__ import annotations

"""Conservative evidence-strength and reporting policy for map/location findings.

This module is intentionally strict about wording:
- Native GPS = EXIF/device metadata only.
- Derived Geo Anchor = coordinates recovered from visible map URL/OCR/context-menu text.
- Map Search Lead = place/landmark text or offline geocoder candidate, not proof.
"""

from dataclasses import asdict, dataclass
from typing import Any


PRIMARY_ANCHOR_KINDS = {"native_gps", "derived_coordinate"}
APPROXIMATE_ANCHOR_KINDS = {"approximate_place", "place_search", "visual_context"}


@dataclass(slots=True)
class LocationClaimPolicy:
    anchor_kind: str
    claim_label: str
    proof_level: str
    report_wording: str
    verification_rule: str
    radius_m: int
    privacy_tier: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("/", " ").split())


def anchor_kind_from_source(source: Any, *, has_native_gps: bool = False, has_coordinates: bool = False) -> str:
    """Classify a geo anchor source without overclaiming.

    ``has_coordinates`` alone is not enough to call something GPS. Offline place
    databases and city centroids also have coordinates, but they are still only
    map/search leads.
    """
    text = _norm(source)
    if has_native_gps or ("native" in text and "gps" in text):
        return "native_gps"
    if any(token in text for token in ("offline geocoder", "geocoder", "centroid", "approximate", "place candidate", "place lead")):
        return "approximate_place"
    if any(token in text for token in ("visible coordinate", "ocr visible coordinate", "map url", "map-url", "derived", "context menu", "right click", "lat", "lon")):
        return "derived_coordinate" if has_coordinates else "place_search"
    if any(token in text for token in ("ocr", "place label", "landmark", "search", "provider link")):
        return "place_search"
    if has_coordinates:
        return "derived_coordinate"
    return "visual_context"


def location_strength_label(
    *,
    has_native_gps: bool = False,
    gps_confidence: int = 0,
    derived_geo_confidence: int = 0,
    map_confidence: int = 0,
    has_map_url: bool = False,
    has_place_dictionary_hit: bool = False,
    basis: list[str] | tuple[str, ...] | None = None,
) -> str:
    basis = list(basis or [])
    if has_native_gps and gps_confidence >= 80:
        return "proof"
    if derived_geo_confidence >= 70 and (has_map_url or "map-url" in basis or "ocr-visible-coordinate" in basis):
        return "lead"
    if map_confidence >= 80 and (has_map_url or has_place_dictionary_hit or "ocr/text" in basis):
        return "lead"
    if map_confidence >= 55 and ("visual-map-colors" in basis or "route-visual" in basis):
        return "weak_signal"
    if map_confidence > 0 or derived_geo_confidence > 0:
        return "weak_signal"
    return "no_signal"


def strength_explanation(label: str) -> str:
    return {
        "proof": "Native GPS or equivalent primary metadata is present and should still be hash-preserved.",
        "lead": "A useful location lead exists, but it needs external corroboration before courtroom wording.",
        "weak_signal": "Only weak/indirect map or OCR context exists; keep it as an investigation pivot.",
        "no_signal": "No reliable location signal was recovered.",
    }.get(label, "Unknown evidence-strength label.")


def confidence_radius_for_anchor(anchor_kind: str, *, confidence: int = 0, source: Any = "") -> int:
    """Return a conservative radius for map previews and reports.

    Approximate city/area/landmark leads must not be drawn like precise GPS.
    """
    source_text = _norm(source)
    confidence = max(0, min(100, int(confidence or 0)))
    if anchor_kind == "native_gps":
        return max(25, int(130 - confidence))
    if anchor_kind == "derived_coordinate":
        return max(80, int(900 - confidence * 6))
    if "landmark" in source_text or "poi" in source_text:
        return 3500 if "approximate" in source_text or "centroid" in source_text else 300
    if "area" in source_text:
        return 4500
    if "city" in source_text:
        return 25000
    if "linear feature" in source_text or "river" in source_text:
        return 12000
    if anchor_kind == "place_search":
        return 8000
    if anchor_kind == "approximate_place":
        return 15000
    return 0


def claim_policy_for_anchor(anchor_kind: str, *, confidence: int = 0, source: Any = "") -> LocationClaimPolicy:
    radius = confidence_radius_for_anchor(anchor_kind, confidence=confidence, source=source)
    if anchor_kind == "native_gps":
        return LocationClaimPolicy(
            anchor_kind=anchor_kind,
            claim_label="Native GPS",
            proof_level="primary_metadata",
            report_wording="Native GPS coordinates were recovered from device/file metadata.",
            verification_rule="Verify timestamp, custody hash, and whether metadata could have been edited before final wording.",
            radius_m=radius,
            privacy_tier="high",
        )
    if anchor_kind == "derived_coordinate":
        return LocationClaimPolicy(
            anchor_kind=anchor_kind,
            claim_label="Derived Geo Anchor",
            proof_level="derived_coordinate_lead",
            report_wording="Coordinates were derived from visible map/OCR/URL evidence; this is not native GPS.",
            verification_rule="Compare against the original screenshot, share URL, app history, or another independent source.",
            radius_m=radius,
            privacy_tier="high",
        )
    if anchor_kind in {"approximate_place", "place_search"}:
        return LocationClaimPolicy(
            anchor_kind=anchor_kind,
            claim_label="Map Search Lead",
            proof_level="approximate_review_required",
            report_wording="A place/landmark candidate was found; coordinates are approximate and review-required.",
            verification_rule="Do not report as exact. Confirm manually with provider review/source-app context.",
            radius_m=radius,
            privacy_tier="medium",
        )
    return LocationClaimPolicy(
        anchor_kind="visual_context",
        claim_label="Map Screenshot Mode",
        proof_level="visual_context_only",
        report_wording="The image looks like map/navigation context, but no stable location anchor was recovered.",
        verification_rule="Run crop OCR on search bar, route card, pins, and labels before making a location claim.",
        radius_m=radius,
        privacy_tier="low",
    )
