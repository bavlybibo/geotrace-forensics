from __future__ import annotations

"""Privacy gate for optional online OSINT/reverse-image workflows."""

from typing import Any, Iterable


def build_online_search_privacy_gate(clues: Iterable[Any], candidates: Iterable[Any], *, allow_image_upload: bool = False) -> dict[str, Any]:
    clue_list = list(clues or [])
    candidate_list = list(candidates or [])
    sensitive_types = []
    for clue in clue_list:
        clue_type = str(getattr(clue, "clue_type", "") or "")
        source = str(getattr(clue, "source", "") or "")
        value = str(getattr(clue, "value", "") or "")
        if clue_type in {"metadata", "map", "country"} or "gps" in source or any(ch.isdigit() for ch in value):
            sensitive_types.append(clue_type or "clue")
    has_coordinates = any(str(getattr(c, "level", "")) == "coordinates" for c in candidate_list)
    return {
        "required_before_online_search": True,
        "offline_default": True,
        "image_upload_allowed": bool(allow_image_upload),
        "has_coordinates": has_coordinates,
        "sensitive_clue_types": sorted(set(sensitive_types)),
        "allowed_modes": [
            "offline_only",
            "manual_text_search_after_review",
            "manual_coordinate_search_after_review",
            "manual_reverse_image_search_after_explicit_approval",
        ],
        "blocked_by_default": [
            "automatic image upload",
            "automatic reverse-image search",
            "automatic external geocoding of private coordinates",
        ],
        "analyst_prompt": "Review extracted text, coordinates, usernames, phone numbers, and image sensitivity before any external OSINT lookup.",
    }
