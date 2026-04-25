from __future__ import annotations

"""Map-specific conservative strength wording."""


def map_strength_label(*, has_native_gps: bool, derived_geo_confidence: int = 0, map_confidence: int = 0) -> str:
    if has_native_gps:
        return "proof"
    if derived_geo_confidence >= 65:
        return "lead"
    if map_confidence >= 70:
        return "lead"
    if map_confidence > 0 or derived_geo_confidence > 0:
        return "weak_signal"
    return "no_signal"
