from __future__ import annotations

from pathlib import Path

from app.agents import AgentRequest, RuleBasedForensicAgent
from app.core.models import EvidenceRecord


def test_rule_based_agent_returns_reviewable_response():
    record = EvidenceRecord(
        case_id="CASE-1",
        case_name="Agent Case",
        evidence_id="IMG-001",
        file_path=Path("image.png"),
        file_name="image.png",
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="abcd000000000000",
        file_size=128,
        imported_at="now",
        source_type="Screenshot",
        confidence_score=62,
    )
    response = RuleBasedForensicAgent().analyze_evidence(
        AgentRequest(
            case_id=record.case_id,
            case_name=record.case_name,
            selected_record=record,
            case_records=(record,),
        )
    )
    assert response.provider.startswith("local-rule-agent")
    assert response.recommended_actions
    assert "Summary" in response.to_panel_text()
