from __future__ import annotations

"""Image Existence Intelligence for CTF/OSINT workflows.

The goal is to answer: has this image or a near-similar image appeared inside the
current case/local evidence set, and does it match known offline landmark clues? It
never performs reverse-image upload automatically.
"""

from pathlib import Path
from typing import Any, Iterable

from .image_fingerprint import fingerprint_image


def _value(record: Any, name: str, default: Any = None) -> Any:
    return getattr(record, name, default)


def build_image_existence_profile(record: Any, landmark_matches: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    path = _value(record, "working_copy_path") or _value(record, "file_path")
    fingerprint: dict[str, Any]
    try:
        fingerprint = fingerprint_image(Path(path)) if path else {"available": False, "note": "No evidence path available."}
    except Exception as exc:
        fingerprint = {"available": False, "method": "local-luminance-8x8", "note": f"Fingerprint error: {exc}"}

    duplicate_group = str(_value(record, "duplicate_group", "") or "")
    similarity_note = str(_value(record, "similarity_note", "") or "")
    perceptual_hash = str(_value(record, "perceptual_hash", "") or "")
    exact_hash = str(_value(record, "sha256", "") or "")
    matches = list(landmark_matches or [])

    exact_duplicate = bool(duplicate_group and duplicate_group not in {"unique", ""})
    note_lower = similarity_note.lower()
    negative_duplicate = any(
        marker in note_lower
        for marker in (
            "no near-duplicate",
            "no near duplicate",
            "no duplicate",
            "no similar",
            "not identified",
            "none identified",
        )
    )
    explicit_near_duplicate = any(
        marker in note_lower
        for marker in (
            "near duplicate detected",
            "near-duplicate detected",
            "similar image detected",
            "similar peer",
            "duplicate peer",
        )
    )
    near_duplicate = bool(duplicate_group and duplicate_group not in {"unique", ""}) or (explicit_near_duplicate and not negative_duplicate)

    return {
        "exact_duplicate_in_case": exact_duplicate,
        "near_duplicate_in_case": near_duplicate,
        "duplicate_group": duplicate_group or "none",
        "perceptual_hash": perceptual_hash,
        "sha256_prefix": exact_hash[:16] if exact_hash else "unavailable",
        "local_fingerprint": fingerprint,
        "known_landmark_match": bool(matches),
        "top_landmark_match": matches[0] if matches else {},
        "reverse_search_status": "Not performed. Manual/privacy-gated only.",
        "recommended_actions": [
            "Compare exact SHA-256 and perceptual hash against authorised local datasets.",
            "Use local landmark matches as leads, not proof, until visually corroborated.",
            "Run reverse-image search only manually and only after privacy approval.",
        ],
    }
