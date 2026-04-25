from __future__ import annotations

from collections import Counter

from .contracts import AgentRequest, AgentResponse


class RuleBasedForensicAgent:
    """Deterministic local agent used as the safe default.

    The agent is intentionally conservative: it turns recovered evidence signals
    into an analyst plan, not an automatic legal conclusion. Future LLM providers
    can replace this class behind the same protocol.
    """

    provider_name = "local-rule-agent-v2"

    def analyze_evidence(self, request: AgentRequest) -> AgentResponse:
        record = request.selected_record
        peers = [item for item in request.case_records if item.evidence_id != record.evidence_id]
        duplicate_peers = [item for item in peers if record.duplicate_group and item.duplicate_group == record.duplicate_group]
        high_risk_peers = [item for item in peers if item.risk_level == "High"]
        source_counts = Counter(item.source_type for item in request.case_records if item.source_type)

        actions: list[str] = []
        caveats: list[str] = [
            "This is a deterministic helper, not a legal conclusion.",
            "Corroborate time, place, and origin with an independent source before reporting.",
        ]

        if record.parser_status != "Valid":
            summary = f"{record.evidence_id} should be structurally verified before content-level conclusions."
            actions.extend([
                "Validate the file with a second parser or external forensic tool.",
                "Preserve source and working-copy hashes before attempting recovery.",
            ])
            confidence = 45
        elif record.ai_flags:
            summary = f"{record.evidence_id} is an AI-prioritized review item: {record.ai_risk_label}."
            actions.extend(record.ai_action_plan[:4] or [
                "Open the AI breakdown and verify each cross-evidence signal manually.",
                "Convert AI flags into a short analyst note with supporting hashes/timestamps.",
            ])
            confidence = max(58, min(86, record.confidence_score + record.ai_confidence))
        elif record.has_gps:
            summary = f"{record.evidence_id} has native GPS and can anchor a map-based reconstruction."
            actions.extend([
                "Open the map package and verify the coordinates against the claimed context.",
                "Compare nearby evidence timestamps to build a travel or event sequence.",
            ])
            confidence = max(70, record.gps_confidence)
        elif record.derived_geo_display != "Unavailable":
            summary = f"{record.evidence_id} has screenshot-derived geo/map clues but no native GPS."
            actions.extend([
                "Treat derived location as a lead, not proof.",
                "Preserve visible map labels, URLs, usernames, and time strings from OCR.",
                "Corroborate the map/place clue with browser history, source app logs, or the original shared map link.",
            ])
            confidence = max(50, min(75, record.derived_geo_confidence))
        elif record.ocr_map_labels or record.possible_geo_clues:
            labels = record.possible_geo_clues or record.ocr_map_labels
            summary = f"{record.evidence_id} has possible map/place text but no stable coordinates. Lead: {labels[0]}."
            actions.extend([
                "Run deep OCR or manually review the screenshot for Arabic/English place labels.",
                "Treat map labels as venue leads only until a URL, browser history entry, or witness/source timeline confirms them.",
                "Avoid marking this as GPS evidence because no native coordinate anchor was recovered.",
            ])
            confidence = max(42, min(68, record.ocr_confidence or record.confidence_score))
        else:
            summary = f"{record.evidence_id} is mainly useful for timeline, source-profile, integrity, and relationship analysis."
            actions.extend([
                "Use timestamp source, source profile, and custody events as the first correlation layer.",
                "Check duplicates and hidden-content signals before assigning evidentiary weight.",
            ])
            confidence = max(35, min(80, record.confidence_score))

        if record.ai_action_plan:
            for item in record.ai_action_plan:
                if item not in actions:
                    actions.append(item)
        if duplicate_peers:
            peer_ids = ", ".join(item.evidence_id for item in duplicate_peers[:5])
            actions.append(f"Review duplicate peer(s) {peer_ids} to decide whether context changed across copies.")
        if record.ai_case_links:
            actions.append("Use the AI case links to build a peer-evidence comparison note.")
        if record.hidden_code_indicators or record.hidden_suspicious_embeds:
            actions.append("Inspect hidden-content findings in a safe viewer before opening any carved payload.")
        if record.risk_level == "High":
            caveats.append("High triage risk means the item deserves review; it does not prove manipulation by itself.")
        if high_risk_peers:
            caveats.append(f"There are {len(high_risk_peers)} other high-risk item(s); do not evaluate this item in isolation.")
        if source_counts:
            dominant, count = source_counts.most_common(1)[0]
            caveats.append(f"Dominant case source profile is {dominant} ({count} item(s)); source outliers need extra explanation.")
        if record.ai_corroboration_matrix:
            caveats.extend(record.ai_corroboration_matrix[:2])

        return AgentResponse(
            summary=summary,
            recommended_actions=actions[:8],
            caveats=caveats[:8],
            confidence=max(0, min(100, confidence)),
            provider=self.provider_name,
        )
