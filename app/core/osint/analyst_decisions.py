from __future__ import annotations

"""Analyst decision contracts for the future OSINT Workbench.

These structures are intentionally UI-independent so decisions can be saved in case
snapshots, reports, and cache files before the full interactive page exists.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


VALID_DECISIONS = {"auto_generated", "verified", "rejected", "needs_review", "promoted", "hidden"}


@dataclass(slots=True)
class AnalystDecision:
    evidence_id: str
    hypothesis_id: str
    decision: str = "auto_generated"
    analyst_note: str = "Tool-generated lead. Analyst review required before external reporting."
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    confidence_override: int | None = None

    def __post_init__(self) -> None:
        if self.decision not in VALID_DECISIONS:
            self.decision = "needs_review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def hypothesis_identifier(evidence_id: str, hypothesis: dict[str, Any], index: int) -> str:
    title = str(hypothesis.get("title", "hypothesis")).lower().replace(" ", "-")[:42]
    strength = str(hypothesis.get("strength", "lead"))
    return f"{evidence_id}:{index:02d}:{title}:{strength}"


def default_decisions_for_hypotheses(evidence_id: str, hypotheses: Iterable[dict[str, Any]]) -> list[AnalystDecision]:
    decisions: list[AnalystDecision] = []
    for index, hypothesis in enumerate(hypotheses):
        strength = str(hypothesis.get("strength", "weak_signal"))
        confidence = int(hypothesis.get("confidence", 0) or 0)
        decision = "needs_review"
        note = "Review and corroborate before external reporting."
        if strength == "proof" and confidence >= 80:
            decision = "auto_generated"
            note = "Strong tool-generated anchor; still validate custody and acquisition context."
        elif strength == "lead":
            decision = "needs_review"
            note = "Lead requires corroboration; do not phrase as fact yet."
        else:
            decision = "needs_review"
            note = "Weak signal; keep as internal pivot unless additional evidence supports it."
        decisions.append(
            AnalystDecision(
                evidence_id=evidence_id,
                hypothesis_id=hypothesis_identifier(evidence_id, hypothesis, index),
                decision=decision,
                analyst_note=note,
            )
        )
    return decisions


def attach_decisions(hypotheses: list[dict[str, Any]], decisions: Iterable[AnalystDecision | dict[str, Any]]) -> list[dict[str, Any]]:
    decision_rows = []
    for decision in decisions:
        decision_rows.append(decision.to_dict() if hasattr(decision, "to_dict") else dict(decision))
    by_id = {str(row.get("hypothesis_id", "")): row for row in decision_rows}
    out: list[dict[str, Any]] = []
    for index, hypothesis in enumerate(hypotheses):
        row = dict(hypothesis)
        hypothesis_id = row.get("hypothesis_id") or hypothesis_identifier(str(row.get("evidence_id", "EV")), row, index)
        row["hypothesis_id"] = hypothesis_id
        row["analyst_decision"] = by_id.get(hypothesis_id, {})
        out.append(row)
    return out
