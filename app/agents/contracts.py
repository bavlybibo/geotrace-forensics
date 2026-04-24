from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, Sequence

try:
    from ..core.models import EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.models import EvidenceRecord


@dataclass(frozen=True)
class AgentRequest:
    """Normalized input sent to any future AI or local forensic agent."""

    case_id: str
    case_name: str
    selected_record: EvidenceRecord
    case_records: Sequence[EvidenceRecord] = field(default_factory=list)
    analyst_context: str = ""


@dataclass(frozen=True)
class AgentResponse:
    """Conservative, reviewable output returned by an agent provider."""

    summary: str
    recommended_actions: List[str]
    caveats: List[str]
    confidence: int
    provider: str = "local-rule-agent"

    def to_panel_text(self) -> str:
        lines = [
            f"Provider: {self.provider}",
            f"Confidence: {self.confidence}%",
            "",
            "Summary:",
            self.summary,
            "",
            "Recommended actions:",
        ]
        lines.extend(f"- {item}" for item in self.recommended_actions)
        lines.extend(["", "Caveats:"])
        lines.extend(f"- {item}" for item in self.caveats)
        return "\n".join(lines)


class ForensicAgent(Protocol):
    """Protocol for plug-in agents: local rules, local LLM, or remote LLM."""

    def analyze_evidence(self, request: AgentRequest) -> AgentResponse:
        """Return a conservative analyst-facing interpretation."""
