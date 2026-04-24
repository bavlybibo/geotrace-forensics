from __future__ import annotations

from .contracts import AgentRequest, AgentResponse


class RuleBasedForensicAgent:
    """Deterministic local agent used as the safe default.

    It gives the UI a stable agent interface today while keeping future LLM
    integration isolated behind the ``ForensicAgent`` protocol.
    """

    provider_name = "local-rule-agent"

    def analyze_evidence(self, request: AgentRequest) -> AgentResponse:
        record = request.selected_record
        actions: list[str] = []
        caveats: list[str] = [
            "This is a deterministic helper, not a legal conclusion.",
            "Corroborate time, place, and origin with an independent source before reporting.",
        ]

        if record.parser_status != "Valid":
            summary = f"{record.evidence_id} needs structural review before content-level conclusions."
            actions.extend([
                "Validate the file with a second parser or external forensic tool.",
                "Preserve source and working-copy hashes before attempting recovery.",
            ])
            confidence = 45
        elif record.has_gps:
            summary = f"{record.evidence_id} has native GPS and can anchor a map-based reconstruction."
            actions.extend([
                "Open the map package and verify the coordinates against the claimed context.",
                "Compare nearby evidence timestamps to build a travel or event sequence.",
            ])
            confidence = max(70, record.gps_confidence)
        elif record.derived_geo_display != "Unavailable":
            summary = f"{record.evidence_id} has screenshot-derived geo clues but no native GPS."
            actions.extend([
                "Treat derived location as a lead, not proof.",
                "Preserve visible map labels, URLs, usernames, and time strings from OCR.",
            ])
            confidence = max(50, min(75, record.derived_geo_confidence))
        else:
            summary = f"{record.evidence_id} is mainly useful for timeline, source-profile, and integrity analysis."
            actions.extend([
                "Use timestamp source, source profile, and custody events as the first correlation layer.",
                "Check duplicates and hidden-content signals before assigning evidentiary weight.",
            ])
            confidence = max(35, min(80, record.confidence_score))

        if record.duplicate_group:
            actions.append("Review duplicate cluster relation to decide whether this is original, reused, or edited media.")
        if record.hidden_code_indicators or record.hidden_suspicious_embeds:
            actions.append("Inspect hidden-content findings in a safe viewer before opening any carved payload.")
        if record.risk_level == "High":
            caveats.append("High triage risk means the item deserves review; it does not prove manipulation by itself.")

        return AgentResponse(
            summary=summary,
            recommended_actions=actions,
            caveats=caveats,
            confidence=max(0, min(100, confidence)),
            provider=self.provider_name,
        )
