from __future__ import annotations

"""Structured offline OSINT pipeline.

This does not call external services. It organizes already-extracted OCR, metadata,
map signals, and visual clues into entities, hypotheses, and corroboration items.
"""

from typing import Any

from .ctf_geolocator import build_ctf_geo_profile
from .entities import extract_osint_entities
from .hypothesis import build_corroboration_matrix, build_location_hypotheses
from .map_url_parser import parse_map_url_signals
from .models import OSINTEntity, OSINTSignalProfile


def _record_texts(record: Any) -> list[str]:
    values: list[str] = []
    for attr in [
        "file_name",
        "visible_text_excerpt",
        "ocr_raw_text",
        "detected_map_context",
        "map_intelligence_summary",
        "osint_content_summary",
    ]:
        value = getattr(record, attr, "")
        if value:
            values.append(str(value))
    for attr in [
        "visible_text_lines",
        "visible_urls",
        "ocr_url_entities",
        "visible_location_strings",
        "ocr_location_entities",
        "ocr_map_labels",
        "place_candidates",
        "landmarks_detected",
    ]:
        values.extend(str(item) for item in getattr(record, attr, []) or [] if str(item or "").strip())
    for region in getattr(record, "ocr_region_signals", []) or []:
        if isinstance(region, dict):
            values.append(str(region.get("text_excerpt", "")))
            values.extend(str(item) for item in region.get("place_hits", []) or [])
    return values


def analyze_osint_signals(record: Any) -> OSINTSignalProfile:
    texts = _record_texts(record)
    entities = extract_osint_entities(texts, source="record-ocr-context")
    map_signals = parse_map_url_signals(texts, source="record-ocr-context")
    for signal in map_signals:
        if signal.raw:
            entities.append(
                # Stored as URL/map entity without duplicating exact raw URL in reports unless privacy level allows it.
                OSINTEntity(
                    value=signal.raw,
                    entity_type="map_signal",
                    source=signal.source,
                    confidence=signal.confidence,
                    sensitivity="location_pivot",
                    note=f"{signal.provider} signal parsed from already-acquired evidence text.",
                )
            )
    hypotheses = build_location_hypotheses(record, map_signals)
    matrix = build_corroboration_matrix(record, hypotheses)
    ctf_profile = build_ctf_geo_profile(record, map_signals)
    return OSINTSignalProfile(entities=entities[:40], hypotheses=hypotheses, corroboration_matrix=matrix, ctf_profile=ctf_profile)
