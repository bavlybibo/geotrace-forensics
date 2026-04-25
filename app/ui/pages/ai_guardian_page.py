from __future__ import annotations

from html import escape

from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from ...core.ai import (
        build_evidence_graph,
        case_readiness_scores,
        explain_contradictions,
        guardian_narrative,
        mini_case_narrative,
        privacy_audit_status,
    )
    from ...core.ocr_diagnostics import run_ocr_diagnostic
except ImportError:  # pragma: no cover
    from app.core.ai import (
        build_evidence_graph,
        case_readiness_scores,
        explain_contradictions,
        guardian_narrative,
        mini_case_narrative,
        privacy_audit_status,
    )
    from app.core.ocr_diagnostics import run_ocr_diagnostic


def _guardian_shell(window, title: str, attr: str, placeholder: str, subtitle: str, height: int) -> QWidget:
    view = window._make_guardian_view(placeholder, height)
    setattr(window, attr, view)
    return window._shell(title, view, subtitle)


def _render_osint_hypothesis_cards(records) -> str:
    cards: list[str] = []
    for record in sorted(records, key=lambda item: (-getattr(item, "osint_content_confidence", 0), item.evidence_id))[:10]:
        hypotheses = getattr(record, "osint_hypothesis_cards", []) or []
        entities = getattr(record, "osint_entities", []) or []
        matrix = getattr(record, "osint_corroboration_matrix", []) or []
        if not hypotheses and getattr(record, "osint_location_hypotheses", []):
            hypotheses = [
                {
                    "title": "Legacy location hypothesis",
                    "claim": text,
                    "strength": "lead",
                    "confidence": getattr(record, "osint_content_confidence", 0),
                    "basis": ["legacy-osint-content"],
                    "limitations": getattr(record, "osint_content_limitations", [])[:2],
                    "next_actions": getattr(record, "osint_next_actions", [])[:2],
                }
                for text in getattr(record, "osint_location_hypotheses", [])[:3]
            ]
        if not hypotheses:
            continue
        entity_preview = ", ".join(
            f"{escape(str(entity.get('entity_type', 'entity')))}:{escape(str(entity.get('value', '')))[:80]}"
            for entity in entities[:4]
        ) or "No sensitive pivots extracted."
        matrix_preview = "<br/>".join(
            f"<b>{escape(str(item.get('status', 'needs_corroboration')))}</b> — missing: {escape(', '.join(str(x) for x in item.get('missing_basis', [])[:4]) or 'none')}"
            for item in matrix[:3]
        ) or "No corroboration matrix generated yet."
        for hypothesis in hypotheses[:4]:
            title = escape(str(hypothesis.get("title", "OSINT hypothesis")))
            claim = escape(str(hypothesis.get("claim", "")))
            strength = escape(str(hypothesis.get("strength", "weak_signal")))
            confidence = escape(str(hypothesis.get("confidence", 0)))
            basis = escape(", ".join(str(x) for x in hypothesis.get("basis", [])[:5]) or "not available")
            limitations = escape(" | ".join(str(x) for x in hypothesis.get("limitations", [])[:2]) or "No major limitation recorded.")
            actions = escape(" | ".join(str(x) for x in hypothesis.get("next_actions", [])[:2]) or "Manual corroboration required.")
            decision = hypothesis.get("analyst_decision", {}) or {}
            decision_text = escape(str(decision.get("decision", "needs_review")))
            decision_note = escape(str(decision.get("analyst_note", "Analyst review required.")))
            cards.append(
                "<div style='border:1px solid #26384a; border-radius:12px; padding:12px; margin:0 0 10px 0; background:#101923;'>"
                f"<div style='font-weight:800; color:#f4f7fb; font-size:14px;'>{escape(record.evidence_id)} • {title}</div>"
                f"<div style='margin-top:5px; color:#d8e2ef;'>{claim}</div>"
                f"<div style='margin-top:8px; color:#9fb2c7;'><b>Strength:</b> {strength} • <b>Confidence:</b> {confidence}% • <b>Basis:</b> {basis}</div>"
                f"<div style='margin-top:6px; color:#c3ceda;'><b>Limitations:</b> {limitations}</div>"
                f"<div style='margin-top:6px; color:#c3ceda;'><b>Next:</b> {actions}</div>"
                f"<div style='margin-top:8px; color:#91a7bd;'><b>Analyst decision:</b> {decision_text} — {decision_note}</div>"
                f"<div style='margin-top:8px; color:#91a7bd;'><b>Entities:</b> {entity_preview}</div>"
                f"<div style='margin-top:6px; color:#91a7bd;'><b>Corroboration:</b><br/>{matrix_preview}</div>"
                "</div>"
            )
    if not cards:
        return "<p>No OSINT hypothesis cards generated yet.</p>"
    return "<h3 style='color:#f4f7fb; margin-top:0;'>Structured OSINT Hypothesis Cards</h3>" + "".join(cards)


def build_ai_guardian_page(window) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    hero = QFrame()
    hero.setObjectName("PanelFrame")
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(16, 16, 16, 16)
    hero_layout.setSpacing(10)

    title = QLabel("AI Guardian")
    title.setObjectName("SectionLabel")
    meta = QLabel(
        "Case readiness, relationship graph, contradiction explanation, OCR readiness, "
        "and privacy-audit checks before export."
    )
    meta.setObjectName("SectionMetaLabel")
    meta.setWordWrap(True)
    hero_layout.addWidget(title)
    hero_layout.addWidget(meta)

    action_row = QHBoxLayout()
    action_row.setSpacing(8)
    window.btn_refresh_ai_guardian = QPushButton("Refresh Guardian")
    window.btn_refresh_ai_guardian.clicked.connect(window.refresh_ai_guardian)
    window.btn_export_ai_guardian = QPushButton("Export Report Package")
    window.btn_export_ai_guardian.clicked.connect(window.generate_reports)
    action_row.addWidget(window.btn_refresh_ai_guardian)
    action_row.addWidget(window.btn_export_ai_guardian)
    action_row.addStretch(1)
    hero_layout.addLayout(action_row)
    layout.addWidget(hero)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(14)

    cards = [
        (
            "Guardian Summary",
            "ai_guardian_summary",
            "Load evidence to generate AI Guardian summary.",
            "Top review queue and strongest AI recommendations.",
            240,
            0,
            0,
        ),
        (
            "Case Readiness Score",
            "ai_readiness_view",
            "Case readiness score will appear here.",
            "Timeline/location/integrity/privacy/courtroom readiness.",
            210,
            0,
            1,
        ),
        (
            "Evidence Strength / Next Actions",
            "ai_strength_view",
            "Evidence strength and next-best-action details will appear here.",
            "Proof vs lead classification, limitations, and recommended corroboration.",
            220,
            1,
            0,
        ),
        (
            "Map Intelligence",
            "ai_map_intelligence_view",
            "Map/route intelligence will appear here.",
            "Google Maps detection, route overlay, candidate city/place, and landmark pivots.",
            220,
            1,
            1,
        ),
        (
            "OSINT Content Reader",
            "ai_osint_content_view",
            "OSINT content understanding will appear here.",
            "What appears inside the image, source context, sensitive pivots, and next actions.",
            220,
            2,
            0,
        ),
        (
            "AI Evidence Graph",
            "ai_graph_view",
            "AI evidence relationship graph will appear here.",
            "Relationship map across duplicates, devices, places, and AI links.",
            260,
            2,
            1,
        ),
        (
            "AI Contradiction Explainer",
            "ai_contradictions_view",
            "Contradiction explainer will appear here.",
            "Human-readable why-this-is-suspicious explanations.",
            220,
            3,
            0,
        ),
        (
            "AI Privacy Auditor",
            "ai_privacy_audit_view",
            "AI Privacy Auditor will appear here.",
            "Pre-export external sharing safety check.",
            200,
            3,
            1,
        ),
        (
            "Tesseract/OCR Startup Diagnostic",
            "ocr_diagnostic_view",
            "OCR/Tesseract diagnostic will appear here.",
            "Detects whether English/Arabic OCR is ready on the demo machine.",
            185,
            4,
            0,
        ),
    ]

    for title, attr, placeholder, subtitle, height, row, col in cards:
        grid.addWidget(_guardian_shell(window, title, attr, placeholder, subtitle, height), row, col)

    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    layout.addLayout(grid)
    layout.addStretch(1)
    return widget


def refresh_ai_guardian_page(window) -> None:
    records = list(getattr(window.case_manager, "records", []))
    try:
        custody_ok, _ = window.case_manager.db.verify_log_chain(window.case_manager.active_case_id)
    except Exception:
        custody_ok = None

    if not records:
        empty = "Load evidence to activate AI Guardian."
        for attr in [
            "ai_guardian_summary",
            "ai_readiness_view",
            "ai_strength_view",
            "ai_graph_view",
            "ai_map_intelligence_view",
            "ai_osint_content_view",
            "ai_contradictions_view",
            "ai_privacy_audit_view",
        ]:
            if hasattr(window, attr):
                getattr(window, attr).setPlainText(empty)
    else:
        readiness = case_readiness_scores(records, custody_ok=custody_ok)
        graph = build_evidence_graph(records)
        contradictions = explain_contradictions(records)
        privacy = privacy_audit_status(records, "redacted_text")

        if hasattr(window, "ai_guardian_summary"):
            window.ai_guardian_summary.setPlainText(
                mini_case_narrative(records) + "\n\n" + guardian_narrative(records, custody_ok=custody_ok, privacy_level="redacted_text")
            )
        if hasattr(window, "ai_readiness_view"):
            window.ai_readiness_view.setPlainText(
                f"Case Readiness: {readiness['case_readiness']}%\n"
                f"Timeline readiness: {readiness['timeline_readiness']}%\n"
                f"Location readiness: {readiness['location_readiness']}%\n"
                f"Integrity readiness: {readiness['integrity_readiness']}%\n"
                f"Privacy readiness: {readiness['privacy_readiness']}%\n"
                f"Courtroom readiness: {readiness['courtroom_readiness']}%\n\n"
                f"{readiness['summary']}"
            )
        if hasattr(window, "ai_strength_view"):
            strength_lines = []
            for record in sorted(records, key=lambda item: (-getattr(item, "evidence_strength_score", 0), item.evidence_id))[:12]:
                reasons = "; ".join(getattr(record, "evidence_strength_reasons", [])[:2]) or "No strength reasons yet."
                limits = "; ".join(getattr(record, "evidence_strength_limitations", [])[:2]) or "No major limitation recorded."
                strength_lines.append(
                    f"{record.evidence_id}: {getattr(record, 'evidence_strength_label', 'weak_signal')} "
                    f"({getattr(record, 'evidence_strength_score', 0)}%) | Next: {getattr(record, 'ai_next_best_action', '') or getattr(record, 'score_next_step', '')}"
                )
                strength_lines.append(f"  Basis: {reasons}")
                strength_lines.append(f"  Limitation: {limits}")
                reasoning = [line for line in getattr(record, "ai_corroboration_matrix", []) if str(line).startswith("AI reasoning:")]
                if reasoning:
                    strength_lines.append("  Deep reasoning: " + " | ".join(str(x).replace("AI reasoning: ", "") for x in reasoning[:2]))
            window.ai_strength_view.setPlainText("\n".join(strength_lines) if strength_lines else "No evidence strength profile generated yet.")
        if hasattr(window, "ai_graph_view"):
            lines = [
                f"{edge.source_id} ↔ {edge.target_id} [{edge.relation}, {edge.weight}%]\n  {edge.reason}"
                for edge in graph[:40]
            ]
            window.ai_graph_view.setPlainText(
                "\n\n".join(lines) if lines else "No meaningful relationships detected yet."
            )
        if hasattr(window, "ai_map_intelligence_view"):
            map_items = [r for r in records if getattr(r, "map_intelligence_confidence", 0) > 0 or getattr(r, "route_overlay_detected", False)]
            if map_items:
                map_lines = []
                for record in sorted(map_items, key=lambda item: (-getattr(item, "map_intelligence_confidence", 0), item.evidence_id))[:8]:
                    route = "Detected" if record.route_overlay_detected else "Not detected"
                    basis = ", ".join(getattr(record, "map_evidence_basis", []) or ["not available"])
                    rankings = getattr(record, "place_candidate_rankings", []) or []
                    map_lines.append(
                        f"{record.evidence_id}: {record.map_app_detected} | {record.map_type} | route {route} ({record.route_confidence}%) | "
                        f"city {record.candidate_city} | area {record.candidate_area} | confidence {record.map_intelligence_confidence}%"
                    )
                    map_lines.append(f"  Evidence basis: {basis}")
                    map_lines.append(f"  OCR note: {getattr(record, 'ocr_note', 'OCR note unavailable.')}")
                    if record.landmarks_detected:
                        map_lines.append("  Landmarks: " + ", ".join(record.landmarks_detected[:4]))
                    if rankings:
                        map_lines.append("  Place ranking: " + " | ".join(rankings[:3]))
                    ladder = getattr(record, "map_evidence_ladder", []) or []
                    if ladder:
                        map_lines.append("  Evidence ladder: " + " | ".join(str(x) for x in ladder[:3]))
                    region_hits = getattr(record, "ocr_region_signals", []) or []
                    if region_hits:
                        compact_regions = []
                        for item in region_hits[:3]:
                            if isinstance(item, dict):
                                compact_regions.append(f"{item.get('region', 'region')}:{item.get('weight', 0)}%:{', '.join(item.get('place_hits', [])[:2]) or 'text'}")
                        if compact_regions:
                            map_lines.append("  Region OCR: " + " | ".join(compact_regions))
                    map_lines.append("  " + record.map_intelligence_summary)
                window.ai_map_intelligence_view.setPlainText("\n".join(map_lines))
            else:
                window.ai_map_intelligence_view.setPlainText("No map/navigation intelligence detected yet.")
        if hasattr(window, "ai_osint_content_view"):
            content_items = [
                r
                for r in records
                if getattr(r, "osint_content_confidence", 0) > 0 or getattr(r, "osint_hypothesis_cards", [])
            ]
            if content_items:
                window.ai_osint_content_view.setHtml(_render_osint_hypothesis_cards(content_items))
            else:
                window.ai_osint_content_view.setPlainText("No OSINT content profile generated yet.")
        if hasattr(window, "ai_contradictions_view"):
            window.ai_contradictions_view.setPlainText(
                "\n\n".join(contradictions)
                if contradictions
                else "No impossible-travel contradiction detected with current anchors."
            )
        if hasattr(window, "ai_privacy_audit_view"):
            osint_sensitive = sum(1 for r in records if getattr(r, "osint_privacy_review", {}).get("records_with_sensitive_osint", 0))
            osint_lines = [
                privacy.get("summary", "Privacy audit unavailable."),
                "",
                f"Structured OSINT privacy review: {osint_sensitive} evidence item(s) contain sensitive OSINT pivots.",
                "Recommended: use Shareable Redacted unless the recipient is authorised for OSINT/location pivots.",
            ]
            window.ai_privacy_audit_view.setPlainText("\n".join(osint_lines))

    if hasattr(window, "ocr_diagnostic_view"):
        try:
            window.ocr_diagnostic_view.setPlainText(run_ocr_diagnostic().to_text())
        except Exception as exc:
            window.ocr_diagnostic_view.setPlainText(f"OCR diagnostic failed: {exc}")
