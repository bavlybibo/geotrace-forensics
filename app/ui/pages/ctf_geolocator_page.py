from __future__ import annotations

"""Compatibility facade for the CTF GeoLocator page.

This module keeps older imports working after moving the real page
implementation into app.ui.pages.ctf.geolocator_page.
"""

from .ctf.geolocator_page import *  # noqa: F401,F403
from .ctf.geolocator_page import build_ctf_geolocator_page, refresh_ctf_geolocator_page


def _candidate_key(candidate):
    """
    Build a stable key for a CTF geolocation candidate.

    This helper is intentionally kept here for backwards compatibility with
    older tests and UI action code that import it from app.ui.pages.ctf_geolocator_page.
    """
    if candidate is None:
        return ""

    if isinstance(candidate, dict):
        for key in ("id", "key", "name", "title", "label", "landmark"):
            value = candidate.get(key)
            if value:
                return str(value).strip().lower()

        parts = [
            candidate.get("city"),
            candidate.get("region"),
            candidate.get("country"),
            candidate.get("source"),
        ]
        joined = "|".join(str(part).strip().lower() for part in parts if part)
        return joined or str(candidate).strip().lower()

    return str(candidate).strip().lower()


def _iter_candidates(payload):
    """
    Safely iterate over candidate records from different result shapes.

    Supports:
    - list of candidates
    - dict with candidates/results/items/answers
    - nested dict sections containing lists
    """
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in (
            "candidates",
            "geo_candidates",
            "location_candidates",
            "answers",
            "results",
            "items",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        collected = []
        for value in payload.values():
            if isinstance(value, list):
                collected.extend(value)
        return collected

    return []


def _update_candidate_status_by_key(candidates, candidate_key, status):
    """
    Update candidate status by stable key.

    Returns True if a candidate was updated, otherwise False.
    """
    if not candidate_key:
        return False

    target_key = str(candidate_key).strip().lower()

    for candidate in _iter_candidates(candidates):
        if isinstance(candidate, dict) and _candidate_key(candidate) == target_key:
            candidate["status"] = status
            return True

    return False


def _render_writeup(candidate):
    """
    Render a clean CTF-ready writeup for a selected candidate.
    """
    if candidate is None:
        return "No candidate selected."

    if not isinstance(candidate, dict):
        return str(candidate)

    title = (
        candidate.get("landmark")
        or candidate.get("name")
        or candidate.get("title")
        or candidate.get("label")
        or "Unknown Candidate"
    )

    location_parts = [
        candidate.get("city"),
        candidate.get("region"),
        candidate.get("country"),
    ]
    location = ", ".join(str(part) for part in location_parts if part)

    confidence = candidate.get("confidence", candidate.get("score", "unknown"))
    evidence = (
        candidate.get("evidence")
        or candidate.get("reason")
        or candidate.get("rationale")
        or candidate.get("explanation")
        or ""
    )

    lines = [
        f"Candidate: {title}",
        f"Location: {location or 'Unknown'}",
        f"Confidence: {confidence}",
    ]

    if evidence:
        lines.append(f"Evidence: {evidence}")

    if candidate.get("flag"):
        lines.append(f"Suggested Flag: {candidate['flag']}")

    return "\n".join(lines)


__all__ = [
    "build_ctf_geolocator_page",
    "refresh_ctf_geolocator_page",
    "_candidate_key",
    "_iter_candidates",
    "_update_candidate_status_by_key",
    "_render_writeup",
]
