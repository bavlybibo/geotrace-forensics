from __future__ import annotations

"""Small JSON cache for structured OSINT outputs.

The cache is conservative: it is keyed by evidence SHA-256 and a schema version, and
it stores only deterministic structured OSINT fields. Analyst decisions remain safe
to persist across case reloads while avoiding repeated OCR/OSINT processing later.
"""

import json
import logging
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "osint-cache-v2-ctf"
LOGGER = logging.getLogger("geotrace.osint.cache")


def _cache_file(cache_dir: Path, evidence_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(evidence_id)) or "evidence"
    return cache_dir / f"{safe_id}.json"


def save_osint_cache(cache_dir: Path, record: Any) -> Path | None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": getattr(record, "evidence_id", ""),
            "sha256": getattr(record, "sha256", ""),
            "osint_entities": getattr(record, "osint_entities", []),
            "osint_hypothesis_cards": getattr(record, "osint_hypothesis_cards", []),
            "osint_corroboration_matrix": getattr(record, "osint_corroboration_matrix", []),
            "osint_analyst_decisions": getattr(record, "osint_analyst_decisions", []),
            "osint_privacy_review": getattr(record, "osint_privacy_review", {}),
            "place_candidate_rankings": getattr(record, "place_candidate_rankings", []),
            "filename_location_hints": getattr(record, "filename_location_hints", []),
            "map_evidence_ladder": getattr(record, "map_evidence_ladder", []),
            "ctf_clues": getattr(record, "ctf_clues", []),
            "geo_candidates": getattr(record, "geo_candidates", []),
            "ctf_search_queries": getattr(record, "ctf_search_queries", []),
            "location_solvability_score": getattr(record, "location_solvability_score", 0),
            "location_solvability_label": getattr(record, "location_solvability_label", "No useful geo clue"),
            "ctf_country_region_profile": getattr(record, "ctf_country_region_profile", "Unknown"),
            "ctf_landmark_matches": getattr(record, "ctf_landmark_matches", []),
            "ctf_writeup": getattr(record, "ctf_writeup", ""),
            "ctf_online_mode_status": getattr(record, "ctf_online_mode_status", "Offline-only."),
            "ctf_image_existence_profile": getattr(record, "ctf_image_existence_profile", {}),
            "ctf_online_privacy_review": getattr(record, "ctf_online_privacy_review", {}),
        }
        path = _cache_file(cache_dir, getattr(record, "evidence_id", "evidence"))
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path
    except Exception as exc:
        LOGGER.warning("Could not write structured OSINT cache for %s: %s", getattr(record, "evidence_id", "evidence"), exc)
        return None


def load_osint_cache(cache_dir: Path, evidence_id: str, *, sha256: str = "") -> dict[str, Any] | None:
    try:
        path = _cache_file(cache_dir, evidence_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            return None
        if sha256 and payload.get("sha256") != sha256:
            return None
        return payload
    except Exception as exc:
        LOGGER.warning("Could not read structured OSINT cache for %s: %s", evidence_id, exc)
        return None
