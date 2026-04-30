from __future__ import annotations

"""Lazy exports for OSINT helpers.

This keeps importing small utility submodules fast and avoids loading the whole
OSINT/CTF pipeline during dependency and system-health checks.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AREA_ALIASES": ("gazetteer", "AREA_ALIASES"),
    "CITY_ALIASES": ("gazetteer", "CITY_ALIASES"),
    "LANDMARK_ALIASES": ("gazetteer", "LANDMARK_ALIASES"),
    "classify_known_places": ("gazetteer", "classify_known_places"),
    "extract_osint_entities": ("entities", "extract_osint_entities"),
    "build_corroboration_matrix": ("hypothesis", "build_corroboration_matrix"),
    "build_location_hypotheses": ("hypothesis", "build_location_hypotheses"),
    "MapURLSignal": ("map_url_parser", "MapURLSignal"),
    "parse_first_coordinate": ("map_url_parser", "parse_first_coordinate"),
    "parse_map_url_signals": ("map_url_parser", "parse_map_url_signals"),
    "AnalystDecision": ("analyst_decisions", "AnalystDecision"),
    "attach_decisions": ("analyst_decisions", "attach_decisions"),
    "default_decisions_for_hypotheses": ("analyst_decisions", "default_decisions_for_hypotheses"),
    "build_ctf_geo_profile": ("ctf_geolocator", "build_ctf_geo_profile"),
    "CorroborationItem": ("models", "CorroborationItem"),
    "CTFClue": ("models", "CTFClue"),
    "CTFGeoProfile": ("models", "CTFGeoProfile"),
    "GeoCandidate": ("models", "GeoCandidate"),
    "OSINTEntity": ("models", "OSINTEntity"),
    "OSINTHypothesis": ("models", "OSINTHypothesis"),
    "OSINTSignalProfile": ("models", "OSINTSignalProfile"),
    "PlaceRank": ("place_ranking", "PlaceRank"),
    "rank_places": ("place_ranking", "rank_places"),
    "rank_places_as_labels": ("place_ranking", "rank_places_as_labels"),
    "build_osint_privacy_review": ("privacy_review", "build_osint_privacy_review"),
    "analyze_osint_signals": ("pipeline", "analyze_osint_signals"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr = _EXPORTS[name]
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value
