from __future__ import annotations

"""Conservative evidence-strength policy for map/location findings."""


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
    if derived_geo_confidence >= 70 and (has_map_url or "map-url" in basis):
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
