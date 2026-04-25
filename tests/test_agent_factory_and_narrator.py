from __future__ import annotations

from pathlib import Path

import pytest

from app.agents import LocalLLMForensicAgent, RuleBasedForensicAgent, build_forensic_agent
from app.core.ai import mini_case_narrative
from app.core.models import EvidenceRecord


def test_agent_factory_defaults_to_local_rule_agent(monkeypatch):
    monkeypatch.delenv("GEOTRACE_AGENT_PROVIDER", raising=False)
    assert isinstance(build_forensic_agent(), RuleBasedForensicAgent)


def test_agent_factory_remote_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GEOTRACE_REMOTE_LLM_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="disabled by default"):
        build_forensic_agent("remote_llm")


def test_agent_factory_local_llm_uses_safe_fallback():
    assert isinstance(build_forensic_agent("local_llm"), LocalLLMForensicAgent)


def test_mini_case_narrator_mentions_map_and_ocr_signals():
    record = EvidenceRecord(
        case_id="CASE-1",
        case_name="Case",
        evidence_id="IMG-001",
        file_path=Path("IMG-001.png"),
        file_name="IMG-001.png",
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=1,
        imported_at="2026-04-24T10:00:00+00:00",
        risk_level="High",
        suspicion_score=70,
        map_intelligence_confidence=82,
        ocr_confidence=65,
        ocr_note="OCR zones recovered from: full/gray. Mode=map_deep. Lang=eng+ara",
    )

    narrative = mini_case_narrative([record])

    assert "Mini Case Narrator" in narrative
    assert "map confidence 82%" in narrative
    assert "OCR confidence 65%" in narrative
