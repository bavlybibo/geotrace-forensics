from __future__ import annotations

"""Pre-export OSINT privacy review helpers."""

from collections import Counter
from typing import Any, Iterable

SENSITIVE_ENTITY_TYPES = {"url", "email", "username", "phone_like", "map_signal"}
LOCATION_TYPES = {"map_signal", "location", "place", "coordinate"}


def build_osint_privacy_review(records: Iterable[Any]) -> dict[str, Any]:
    entity_counter: Counter[str] = Counter()
    location_pivots = 0
    hypothesis_count = 0
    high_confidence_leads = 0
    records_with_sensitive_osint = 0

    for record in records:
        sensitive_in_record = False
        entities = getattr(record, "osint_entities", []) or []
        for entity in entities:
            entity_type = str(entity.get("entity_type", "entity")) if isinstance(entity, dict) else str(getattr(entity, "entity_type", "entity"))
            sensitivity = str(entity.get("sensitivity", "") if isinstance(entity, dict) else getattr(entity, "sensitivity", ""))
            entity_counter[entity_type] += 1
            if entity_type in SENSITIVE_ENTITY_TYPES or sensitivity in {"location_pivot", "personal_data", "external_pivot"}:
                sensitive_in_record = True
            if entity_type in LOCATION_TYPES or sensitivity == "location_pivot":
                location_pivots += 1
        hypotheses = getattr(record, "osint_hypothesis_cards", []) or []
        hypothesis_count += len(hypotheses)
        for hypothesis in hypotheses:
            if int(hypothesis.get("confidence", 0) or 0) >= 70 and str(hypothesis.get("strength", "")) in {"lead", "proof"}:
                high_confidence_leads += 1
                sensitive_in_record = True
        if getattr(record, "derived_geo_display", "Unavailable") != "Unavailable" or getattr(record, "map_intelligence_confidence", 0) > 0:
            location_pivots += 1
            sensitive_in_record = True
        if sensitive_in_record:
            records_with_sensitive_osint += 1

    recommended_mode = "redacted_text" if records_with_sensitive_osint else "path_only"
    warning = "OSINT pivots include sensitive location/external identifiers; review before sharing." if records_with_sensitive_osint else "No high-risk OSINT pivots were detected."
    return {
        "records_with_sensitive_osint": records_with_sensitive_osint,
        "hypothesis_count": hypothesis_count,
        "high_confidence_leads": high_confidence_leads,
        "location_pivots": location_pivots,
        "entity_counts": dict(entity_counter),
        "recommended_export_mode": recommended_mode,
        "warning": warning,
        "actions": [
            "Use Internal Full only for authorised analysts.",
            "Use Shareable Redacted for external review unless the recipient is authorised to see OSINT pivots.",
            "Exclude or redact OSINT Appendix when location/user pivots are not necessary.",
        ] if records_with_sensitive_osint else ["Path-only redaction is sufficient for routine internal review."],
    }
