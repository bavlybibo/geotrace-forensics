from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

AI_PROVIDER_NAME = "GeoTrace Local AI Analyst v4"


@dataclass
class BatchAIFinding:
    provider: str = AI_PROVIDER_NAME
    score_delta: int = 0
    confidence_delta: int = 0
    label: str = "No batch-level AI flags"
    summary: str = "AI batch assessment completed; no cross-evidence anomaly was identified for this item."
    flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    breakdown: List[str] = field(default_factory=list)
    action_plan: List[str] = field(default_factory=list)
    corroboration_matrix: List[str] = field(default_factory=list)
    case_links: List[str] = field(default_factory=list)
    evidence_graph: List[str] = field(default_factory=list)
    contradiction_explainer: List[str] = field(default_factory=list)
    courtroom_readiness: str = "Ready for courtroom: Pending AI review."
    next_best_action: str = "No AI next-best-action generated yet."
    privacy_audit: str = "AI privacy auditor has not run yet."
    executive_note: str = "No AI priority note generated yet."
    priority_rank: int = 0
    evidence_strength: str = "weak_signal"
    evidence_strength_score: int = 0
    evidence_strength_reasons: List[str] = field(default_factory=list)
    evidence_strength_limitations: List[str] = field(default_factory=list)
    confidence_basis: List[str] = field(default_factory=list)

    def add(
        self,
        *,
        flag: str,
        reason: str,
        contributor: str,
        delta: int,
        confidence_delta: int = 2,
        breakdown_detail: Optional[str] = None,
        case_link: Optional[str] = None,
    ) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
        if contributor not in self.contributors:
            self.contributors.append(contributor)
        if reason not in self.reasons:
            self.reasons.append(reason)
        self.score_delta += max(0, delta)
        self.confidence_delta += max(0, confidence_delta)
        detail = f"AI +{max(0, delta)} — {breakdown_detail or reason}"
        if detail not in self.breakdown:
            self.breakdown.append(detail)
        if case_link and case_link not in self.case_links:
            self.case_links.append(case_link)
        self.refresh_label()

    def add_action(self, action: str) -> None:
        clean = action.strip()
        if clean and clean not in self.action_plan:
            self.action_plan.append(clean)

    def add_matrix_line(self, line: str) -> None:
        clean = line.strip()
        if clean and clean not in self.corroboration_matrix:
            self.corroboration_matrix.append(clean)

    def add_link(self, link: str) -> None:
        clean = link.strip()
        if clean and clean not in self.case_links:
            self.case_links.append(clean)

    def add_graph_line(self, line: str) -> None:
        clean = line.strip()
        if clean and clean not in self.evidence_graph:
            self.evidence_graph.append(clean)

    def add_contradiction(self, line: str) -> None:
        clean = line.strip()
        if clean and clean not in self.contradiction_explainer:
            self.contradiction_explainer.append(clean)

    def refresh_label(self) -> None:
        if self.score_delta >= 28 or len(self.flags) >= 4:
            self.label = "Critical AI review priority"
        elif self.score_delta >= 18 or len(self.flags) >= 2:
            self.label = "High AI review priority"
        elif self.score_delta >= 8 or self.flags:
            self.label = "AI review recommended"
        else:
            self.label = "No batch-level AI flags"
        if self.flags:
            self.summary = f"{self.label}: " + "; ".join(self.reasons[:3])

    def finalize(self) -> None:
        self.score_delta = max(0, min(35, int(self.score_delta)))
        self.confidence_delta = max(0, min(12, int(self.confidence_delta)))
        self.action_plan = self.action_plan[:6]
        self.corroboration_matrix = self.corroboration_matrix[:8]
        self.case_links = self.case_links[:8]
        self.evidence_graph = self.evidence_graph[:10]
        self.contradiction_explainer = self.contradiction_explainer[:6]
        self.evidence_strength_reasons = self.evidence_strength_reasons[:6]
        self.evidence_strength_limitations = self.evidence_strength_limitations[:6]
        self.confidence_basis = self.confidence_basis[:10]
        self.refresh_label()
        if self.evidence_strength_reasons:
            self.add_matrix_line(
                f"Evidence strength: {self.evidence_strength} ({self.evidence_strength_score}%) — "
                + "; ".join(self.evidence_strength_reasons[:3])
            )
        if self.evidence_strength_limitations:
            self.add_action("Resolve evidence-strength limitation: " + self.evidence_strength_limitations[0])
        if self.next_best_action == "No AI next-best-action generated yet." and self.action_plan:
            self.next_best_action = self.action_plan[0]
        if self.flags:
            self.executive_note = f"Review this item because {self.reasons[0] if self.reasons else 'one or more cross-evidence signals require review'}"
        elif self.action_plan:
            self.executive_note = f"No AI anomaly flag. First recommended corroboration step: {self.action_plan[0]}"
        else:
            self.executive_note = "No AI anomaly flag. Manual review can continue with normal timeline and integrity checks."
