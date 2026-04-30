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


def _metric_pill(window, label_text: str, value_attr: str, note_attr: str, value_text: str = "—", note_text: str = "Awaiting evidence") -> QFrame:
    frame = QFrame()
    frame.setObjectName("MetricPill")
    role_map = {"High Risk": "danger", "Image AI": "ai", "Privacy": "privacy", "Readiness": "ready", "Evidence": "evidence"}
    frame.setProperty("role", role_map.get(label_text, "neutral"))
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(3)
    label = QLabel(label_text)
    label.setObjectName("MetricPillLabel")
    value = QLabel(value_text)
    value.setObjectName("MetricPillValue")
    note = QLabel(note_text)
    note.setObjectName("MetricPillNote")
    note.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(value)
    layout.addWidget(note)
    setattr(window, value_attr, value)
    setattr(window, note_attr, note)
    return frame


def _mini_card(title: str, value: str, note: str = "", tone: str = "#84dcff") -> str:
    return (
        "<div style='border:1px solid #24384c;border-radius:14px;padding:12px;margin:0 8px 10px 0;background:#0d1722;'>"
        f"<div style='color:{tone};font-weight:900;font-size:13px;'>{escape(title)}</div>"
        f"<div style='color:#f4f7fb;font-weight:800;font-size:18px;margin-top:4px;'>{escape(value)}</div>"
        f"<div style='color:#9fb2c7;margin-top:6px;'>{escape(note)}</div>"
        "</div>"
    )


def _risk_palette(label: str, *, dangerous: bool = False) -> dict[str, str]:
    label = str(label or "SAFE").upper()
    if label == "CRITICAL" or dangerous:
        return {"border": "#ff4d7d", "bg": "#23101a", "title": "#ffd5df", "accent": "#ff6d96", "text": "#ffeef4", "muted": "#d8a9b8"}
    if label == "HIGH":
        return {"border": "#ff8a4c", "bg": "#24160e", "title": "#ffe0c7", "accent": "#ffad6b", "text": "#fff2e8", "muted": "#d8b79f"}
    if label == "MEDIUM":
        return {"border": "#ffd166", "bg": "#211b0e", "title": "#fff1bc", "accent": "#ffd166", "text": "#fff9df", "muted": "#d7c487"}
    if label == "LOW":
        return {"border": "#3de0a7", "bg": "#0d1d18", "title": "#c7ffe9", "accent": "#66efbd", "text": "#eafff6", "muted": "#97d6bd"}
    return {"border": "#37c6ff", "bg": "#0b1721", "title": "#dff7ff", "accent": "#8de9ff", "text": "#edfaff", "muted": "#9ebed2"}


def _payload_value(record, key: str, default=None):
    payload = getattr(record, "image_risk_verdict_payload", {}) or {}
    attr = f"image_risk_{key}"
    return getattr(record, attr, payload.get(key, default))


def _render_image_triage_deck(records) -> str:
    """Compact command deck for the calibrated image AI decision layer."""
    rows = [r for r in records if int(getattr(r, "image_risk_score", 0) or 0) > 0 or getattr(r, "image_risk_is_dangerous", False)]
    if not rows:
        return (
            "<div style='border:1px solid #214461;border-radius:16px;padding:14px;background:#0a1520;'>"
            "<div style='color:#9ee6bc;font-weight:950;font-size:15px;'>No active image triage queue</div>"
            "<div style='color:#9fb2c7;margin-top:8px;'>Load/analyze images to populate calibrated SAFE/LOW/MEDIUM/HIGH decisions, review priority, evidence grade, and export policy.</div>"
            "</div>"
        )
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    label_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SAFE": 4}
    cards: list[str] = []
    for record in sorted(
        rows,
        key=lambda item: (
            priority_rank.get(str(_payload_value(item, "review_priority", "P3")), 9),
            label_rank.get(str(getattr(item, "image_risk_label", "SAFE")).upper(), 9),
            -int(getattr(item, "image_risk_score", 0) or 0),
            item.evidence_id,
        ),
    )[:8]:
        label = str(getattr(record, "image_risk_label", "SAFE")).upper()
        palette = _risk_palette(label, dangerous=bool(getattr(record, "image_risk_is_dangerous", False)))
        grade = escape(str(_payload_value(record, "evidence_grade", "D")))
        priority = escape(str(_payload_value(record, "review_priority", "P3")))
        temp = escape(str(_payload_value(record, "risk_temperature", "COOL")))
        score = escape(str(getattr(record, "image_risk_score", 0)))
        conf = escape(str(getattr(record, "image_risk_confidence", 0)))
        family = escape(str(_payload_value(record, "threat_family", "clean")))
        lane = escape(str(_payload_value(record, "decision_lane", "benign_or_normal_preservation")))
        handling = escape(str(_payload_value(record, "safe_handling_profile", "normal_evidence_preservation")))
        export = escape(str(_payload_value(record, "export_policy", "Shareable after standard case redaction.")))
        technical_threat = escape(str(_payload_value(record, "technical_threat", "Low")))
        privacy_exposure = escape(str(_payload_value(record, "privacy_exposure", "Low")))
        geo_sensitivity = escape(str(_payload_value(record, "geo_sensitivity", "Low")))
        manipulation_suspicion = escape(str(_payload_value(record, "manipulation_suspicion", "Low")))
        missing = _payload_value(record, "missing_evidence", []) or []
        calibration = _payload_value(record, "calibration_notes", []) or []
        missing_line = escape(" | ".join(str(x) for x in list(missing)[:3]) or "No major missing evidence note.")
        calibration_line = escape(" | ".join(str(x) for x in list(calibration)[:4]) or "No calibration notes.")
        primary = escape(str(getattr(record, "image_risk_primary_reason", "No primary reason recorded.")))
        cards.append(
            f"<div style='border:1px solid {palette['border']};border-radius:16px;padding:13px;margin:0 0 12px 0;background:{palette['bg']};'>"
            f"<div style='display:flex;justify-content:space-between;gap:8px;'>"
            f"<div style='color:{palette['title']};font-weight:950;'>{escape(record.evidence_id)} • {escape(label)} {score}%</div>"
            f"<div style='color:{palette['accent']};font-weight:950;'>Grade {grade} • {priority} • {temp}</div>"
            "</div>"
            f"<div style='margin-top:7px;color:{palette['text']};'><b>Lane:</b> {lane} • <b>Family:</b> {family} • <b>Confidence:</b> {conf}%</div>"
            f"<div style='margin-top:7px;color:{palette['text']};'><b>Technical:</b> {technical_threat} • <b>Privacy:</b> {privacy_exposure} • <b>Geo:</b> {geo_sensitivity} • <b>Manipulation:</b> {manipulation_suspicion}</div>"
            f"<div style='margin-top:7px;color:{palette['muted']};'><b>Reason:</b> {primary}</div>"
            f"<div style='margin-top:7px;color:{palette['text']};'><b>Handling:</b> {handling}</div>"
            f"<div style='margin-top:7px;color:#c9d7e6;'><b>Missing evidence:</b> {missing_line}</div>"
            f"<div style='margin-top:7px;color:#9fb2c7;'><b>Calibration:</b> {calibration_line}</div>"
            f"<div style='margin-top:7px;color:{palette['accent']};'><b>Export policy:</b> {export}</div>"
            "</div>"
        )
    return "".join(cards)


def _render_guardian_summary_cards(records, readiness: dict, custody_ok, privacy: dict) -> str:
    high = sum(1 for record in records if getattr(record, "risk_level", "Low") == "High" or getattr(record, "image_risk_is_dangerous", False))
    ai_flagged = sum(1 for record in records if getattr(record, "ai_flags", []))
    map_items = sum(1 for record in records if getattr(record, "map_intelligence_confidence", 0) > 0)
    ocr_ready = sum(1 for record in records if getattr(record, "ocr_confidence", 0) > 0)
    dangerous_images = sum(1 for record in records if getattr(record, "image_risk_is_dangerous", False))
    review_images = sum(1 for record in records if getattr(record, "image_risk_label", "SAFE") in {"MEDIUM", "HIGH", "CRITICAL"})
    strongest = max(records, key=lambda item: getattr(item, "evidence_strength_score", 0), default=None)
    custody_text = "Verified" if custody_ok is True else "Needs review" if custody_ok is False else "Not checked"
    cards = [
        _mini_card("Case Readiness", f"{readiness.get('case_readiness', 0)}%", readiness.get("summary", "Readiness unavailable.")[:140]),
        _mini_card("Custody Chain", custody_text, "Audit-chain state for the active case."),
        _mini_card("High-risk Queue", str(high), f"AI/manual review flagged {ai_flagged} item(s)."),
        _mini_card("Map/OCR Signals", f"{map_items} map • {ocr_ready} OCR", "Use OCR/map leads as triage unless corroborated."),
        _mini_card("Image Threat AI", f"{dangerous_images} dangerous • {review_images} review", "Direct SAFE/LOW/MEDIUM/HIGH/CRITICAL image judgement.", "#ffb0c8" if dangerous_images else "#f9d98d" if review_images else "#9ee6bc"),
    ]
    top_lines = []
    if strongest is not None:
        top_lines.append(
            f"<li><b>{escape(getattr(strongest, 'evidence_id', 'EV'))}</b> — "
            f"{escape(getattr(strongest, 'evidence_strength_label', 'weak_signal'))} "
            f"({escape(str(getattr(strongest, 'evidence_strength_score', 0)))}%). "
            f"Next: {escape(getattr(strongest, 'ai_next_best_action', '') or getattr(strongest, 'score_next_step', 'Manual review required.'))}</li>"
        )
    for record in sorted(records, key=lambda item: (-getattr(item, "suspicion_score", 0), item.evidence_id))[:4]:
        top_lines.append(
            f"<li><b>{escape(record.evidence_id)}</b> — risk {escape(record.risk_level)} / score {record.suspicion_score}. "
            f"{escape((getattr(record, 'score_primary_issue', '') or getattr(record, 'metadata_issue_summary', ''))[:160])}</li>"
        )
    privacy_summary = escape(str(privacy.get("summary", "Privacy audit unavailable.")))
    return (
        "<div style='display:grid;grid-template-columns:repeat(2, minmax(0,1fr));gap:8px;'>" + "".join(cards) + "</div>"
        "<div style='border:1px solid #24384c;border-radius:14px;padding:12px;background:#0b1420;margin-top:8px;'>"
        "<div style='color:#84dcff;font-weight:900;'>Top Review Queue</div>"
        f"<ul style='margin-top:8px;color:#dff6ff;'>{''.join(top_lines) if top_lines else '<li>No evidence loaded.</li>'}</ul>"
        f"<div style='color:#9fb2c7;margin-top:8px;'><b>Privacy:</b> {privacy_summary}</div>"
        "</div>"
    )


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
    image_cards: list[str] = []
    for record in sorted(records, key=lambda item: (-getattr(item, "image_detail_confidence", 0), item.evidence_id))[:10]:
        if getattr(record, "image_detail_confidence", 0) <= 0:
            continue
        layout = escape(" | ".join(str(x) for x in getattr(record, "image_layout_hints", [])[:3]) or "No layout hints recorded.")
        objects = escape(" | ".join(str(x) for x in getattr(record, "image_object_hints", [])[:3]) or "No object-like hints recorded.")
        quality = escape(" | ".join(str(x) for x in getattr(record, "image_quality_flags", [])[:3]) or "No major quality flags recorded.")
        descriptors = escape(" | ".join(str(x) for x in getattr(record, "image_scene_descriptors", [])[:3]) or "No scene descriptors recorded.")
        methodology = escape(" | ".join(str(x) for x in getattr(record, "image_analysis_methodology", [])[:2]) or "No image methodology generated.")
        metrics = dict(getattr(record, "image_detail_metrics", {}) or {})
        strategy = escape(str(metrics.get("analysis_strategy", "balanced visual review")))
        score_line = escape(
            f"OCR {metrics.get('ocr_priority_score', 0)} • "
            f"Map {metrics.get('map_review_priority_score', 0)} • "
            f"Geo {metrics.get('geolocation_potential_score', 0)} • "
            f"Hidden {metrics.get('hidden_content_priority_score', 0)} • "
            f"Gate {metrics.get('quality_gate', 'ready_for_triage')}"
        )
        target = escape(str(metrics.get("corroboration_target", "baseline packet")))
        region_lines = []
        for region in (getattr(record, "image_attention_regions", []) or [])[:3]:
            if isinstance(region, dict):
                region_lines.append(
                    f"{region.get('region', '?')} score {region.get('attention_score', 0)} box={region.get('original_box', [])} "
                    f"({', '.join(str(x) for x in (region.get('reasons', []) or [])[:2])})"
                )
        regions = escape(" | ".join(region_lines) or "No attention regions recorded.")
        image_cards.append(
            "<div style='border:1px solid #2f4660; border-radius:12px; padding:12px; margin:0 0 10px 0; background:#0f1722;'>"
            f"<div style='font-weight:900; color:#b8e7ff; font-size:14px;'>{escape(record.evidence_id)} • Deep Image Intelligence</div>"
            f"<div style='margin-top:5px; color:#e4f7ff;'><b>{escape(getattr(record, 'image_detail_label', 'Unavailable'))}</b> — {escape(str(getattr(record, 'image_detail_confidence', 0)))}%</div>"
            f"<div style='margin-top:6px; color:#c4d5e6;'>{escape(getattr(record, 'image_detail_summary', 'Image detail unavailable.'))}</div>"
            f"<div style='margin-top:6px; color:#bdeeff;'><b>Reasoning strategy:</b> {strategy} — {score_line}</div>"
            f"<div style='margin-top:6px; color:#a9d7e8;'><b>Corroboration target:</b> {target}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Scene descriptors:</b> {descriptors}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Attention regions:</b> {regions}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Layout:</b> {layout}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Object/scene hints:</b> {objects}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Quality:</b> {quality}</div>"
            f"<div style='margin-top:6px; color:#a9bdcf;'><b>Methodology:</b> {methodology}</div>"
            "</div>"
        )

    threat_cards: list[str] = []
    threat_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SAFE": 4}
    for record in sorted(records, key=lambda item: (threat_rank.get(getattr(item, "image_risk_label", "SAFE"), 9), -getattr(item, "image_risk_score", 0), item.evidence_id))[:10]:
        label = str(getattr(record, "image_risk_label", "SAFE")).upper()
        if label == "SAFE" and getattr(record, "image_risk_score", 0) <= 0:
            continue
        palette = _risk_palette(label, dangerous=bool(getattr(record, "image_risk_is_dangerous", False)))
        badge = escape(str(getattr(record, "image_risk_badge", label)))
        score = escape(str(getattr(record, "image_risk_score", 0)))
        conf = escape(str(getattr(record, "image_risk_confidence", 0)))
        summary = escape(str(getattr(record, "image_risk_summary", "No image risk judgement generated.")))
        primary = escape(str(getattr(record, "image_risk_primary_reason", "No primary reason recorded.")))
        zones = escape(" | ".join(str(x) for x in getattr(record, "image_risk_danger_zones", [])[:4]) or "none")
        privacy = escape(" | ".join(str(x) for x in getattr(record, "image_risk_privacy_findings", [])[:3]) or "none")
        guards = escape(" | ".join(str(x) for x in getattr(record, "image_risk_false_positive_guards", [])[:3]) or "No guardrail triggered.")
        evidence = escape(" | ".join(str(x) for x in getattr(record, "image_risk_evidence_matrix", [])[:3]) or "No direct image-threat evidence recorded.")
        actions = escape(" | ".join(str(x) for x in getattr(record, "image_risk_next_actions", [])[:3]) or "No specific action generated.")
        family = escape(str(_payload_value(record, "threat_family", "clean")))
        lane = escape(str(_payload_value(record, "decision_lane", "benign_or_normal_preservation")))
        sensors = escape(str(_payload_value(record, "technical_signal_count", 0)))
        hint = escape(str(_payload_value(record, "analyst_verdict_hint", "No hint generated.")))
        contributors = _payload_value(record, "contributor_matrix", []) or []
        contributors_line = escape(" | ".join(str(x) for x in list(contributors)[:3]) or "No weighted contributors available.")
        grade = escape(str(_payload_value(record, "evidence_grade", "D")))
        priority = escape(str(_payload_value(record, "review_priority", "P3")))
        temperature = escape(str(_payload_value(record, "risk_temperature", "COOL")))
        handling = escape(str(_payload_value(record, "safe_handling_profile", "normal_evidence_preservation")))
        export_policy = escape(str(_payload_value(record, "export_policy", "Shareable after standard case redaction.")))
        missing = _payload_value(record, "missing_evidence", []) or []
        calibration = _payload_value(record, "calibration_notes", []) or []
        missing_line = escape(" | ".join(str(x) for x in list(missing)[:2]) or "No major missing evidence note.")
        calibration_line = escape(" | ".join(str(x) for x in list(calibration)[:3]) or "No calibration notes.")
        dangerous_text = "YES — isolate" if getattr(record, "image_risk_is_dangerous", False) else "NO — controlled review/normal preservation"
        threat_cards.append(
            f"<div style='border:1px solid {palette['border']}; border-radius:14px; padding:13px; margin:0 0 12px 0; background:{palette['bg']};'>"
            f"<div style='display:flex; justify-content:space-between; gap:8px;'>"
            f"<div style='font-weight:950; color:{palette['title']}; font-size:14px;'>{escape(record.evidence_id)} • Image Threat AI</div>"
            f"<div style='color:{palette['accent']}; font-weight:950;'>{escape(label)} / {badge}</div>"
            "</div>"
            f"<div style='margin-top:6px; color:{palette['text']};'><b>Dangerous:</b> {dangerous_text} • score {score}% • confidence {conf}% • sensors {sensors}</div>"
            f"<div style='margin-top:7px; color:{palette['muted']};'>{summary}</div>"
            f"<div style='margin-top:7px; color:{palette['text']};'><b>Grade:</b> {grade} • <b>Priority:</b> {priority} • <b>Temp:</b> {temperature}</div>"
            f"<div style='margin-top:7px; color:{palette['text']};'><b>Lane:</b> {lane} • <b>Family:</b> {family}</div>"
            f"<div style='margin-top:7px; color:{palette['muted']};'><b>Primary reason:</b> {primary}</div>"
            f"<div style='margin-top:7px; color:{palette['muted']};'><b>Danger zones:</b> {zones}</div>"
            f"<div style='margin-top:7px; color:{palette['muted']};'><b>Evidence:</b> {evidence}</div>"
            f"<div style='margin-top:7px; color:{palette['muted']};'><b>Top contributors:</b> {contributors_line}</div>"
            f"<div style='margin-top:7px; color:{palette['text']};'><b>Handling:</b> {handling}</div>"
            f"<div style='margin-top:7px; color:#c9d7e6;'><b>Missing evidence:</b> {missing_line}</div>"
            f"<div style='margin-top:7px; color:#9fb2c7;'><b>Calibration:</b> {calibration_line}</div>"
            f"<div style='margin-top:7px; color:#9fb2c7;'><b>Privacy:</b> {privacy}</div>"
            f"<div style='margin-top:7px; color:#8fa1b2;'><b>Guardrails:</b> {guards}</div>"
            f"<div style='margin-top:7px; color:{palette['text']};'><b>Analyst hint:</b> {hint}</div>"
            f"<div style='margin-top:7px; color:{palette['accent']};'><b>Export policy:</b> {export_policy}</div>"
            f"<div style='margin-top:7px; color:{palette['accent']};'><b>Next:</b> {actions}</div>"
            "</div>"
        )
    pixel_cards: list[str] = []
    call_rank = {"ISOLATE": 0, "REVIEW": 1, "WATCH": 2, "CLEAR": 3}
    for record in sorted(records, key=lambda item: (call_rank.get(getattr(item, "digital_final_call", "CLEAR"), 9), -getattr(item, "digital_risk_score", 0), item.evidence_id))[:10]:
        if (
            getattr(record, "digital_final_call", "CLEAR") == "CLEAR"
            and getattr(record, "pixel_hidden_score", 0) < 15
            and not getattr(record, "pixel_lsb_strings", [])
        ):
            continue
        zones = escape(" | ".join(str(x) for x in getattr(record, "digital_danger_zones", [])[:4]) or "none")
        evidence = escape(" | ".join(str(x) for x in getattr(record, "digital_evidence_brief", [])[:3]) or "No focused evidence recorded.")
        guards = escape(" | ".join(str(x) for x in getattr(record, "digital_false_positive_guards", [])[:2]) or "No extra guardrails triggered.")
        call = escape(str(getattr(record, "digital_final_call", "CLEAR")))
        risk = escape(str(getattr(record, "digital_risk_score", 0)))
        conf = escape(str(getattr(record, "digital_confidence_score", 0)))
        one_line = escape(str(getattr(record, "digital_one_line", "No digital-risk verdict generated.")))
        pixel_cards.append(
            "<div style='border:1px solid #4a3140; border-radius:12px; padding:12px; margin:0 0 10px 0; background:#1b1018;'>"
            f"<div style='font-weight:900; color:#ffd6f0; font-size:14px;'>{escape(record.evidence_id)} • Digital Risk Verdict</div>"
            f"<div style='margin-top:5px; color:#f3e4ee;'><b>{call}</b> — risk {risk}% / confidence {conf}%</div>"
            f"<div style='margin-top:6px; color:#cdb8c6;'>{one_line}</div>"
            f"<div style='margin-top:6px; color:#bda6b5;'><b>Danger zone:</b> {zones}</div>"
            f"<div style='margin-top:6px; color:#bda6b5;'><b>Evidence:</b> {evidence}</div>"
            f"<div style='margin-top:6px; color:#8fa1b2;'><b>Guardrails:</b> {guards}</div>"
            "</div>"
        )
    if not cards and not pixel_cards and not image_cards and not threat_cards:
        return "<p>No OSINT hypothesis cards generated yet.</p>"
    output = "<h3 style='color:#f4f7fb; margin-top:0;'>Structured OSINT Hypothesis Cards</h3>"
    if image_cards:
        output += "<h3 style='color:#8de9ff;'>Deep Image Intelligence</h3>" + "".join(image_cards)
    if threat_cards:
        output += "<h3 style='color:#ff9fbd;'>Image Threat AI — Danger / Privacy / False-positive Lane</h3>" + "".join(threat_cards)
    if pixel_cards:
        output += "<h3 style='color:#ffd166;'>Digital Risk Verdicts</h3>" + "".join(pixel_cards)
    return output + "".join(cards)


def build_ai_guardian_page(window) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    hero = QFrame()
    hero.setObjectName("AIGuardianHero")
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

    metrics = QHBoxLayout()
    metrics.setSpacing(10)
    metrics.addWidget(_metric_pill(window, "Evidence", "ai_metric_evidence_value", "ai_metric_evidence_note", "0", "No evidence loaded."))
    metrics.addWidget(_metric_pill(window, "Readiness", "ai_metric_readiness_value", "ai_metric_readiness_note", "0%", "Overall case readiness."))
    metrics.addWidget(_metric_pill(window, "High Risk", "ai_metric_risk_value", "ai_metric_risk_note", "0", "Priority review queue."))
    metrics.addWidget(_metric_pill(window, "Image AI", "ai_metric_image_value", "ai_metric_image_note", "SAFE", "No image danger judgement yet."))
    metrics.addWidget(_metric_pill(window, "Privacy", "ai_metric_privacy_value", "ai_metric_privacy_note", "—", "Export posture."))
    hero_layout.addLayout(metrics)

    action_row = QHBoxLayout()
    action_row.setSpacing(8)
    window.btn_refresh_ai_guardian = QPushButton("Refresh Guardian")
    window.btn_refresh_ai_guardian.setObjectName("AIPrimaryButton")
    window.btn_refresh_ai_guardian.clicked.connect(window.refresh_ai_guardian)
    window.btn_export_ai_guardian = QPushButton("Export Report Package")
    window.btn_export_ai_guardian.setObjectName("AIExportButton")
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
            "Image AI Triage Queue",
            "ai_image_triage_view",
            "Image AI triage queue will appear here.",
            "Calibrated evidence grade, review priority, risk temperature, safe handling, and export policy.",
            250,
            0,
            1,
        ),
        (
            "Case Readiness Score",
            "ai_readiness_view",
            "Case readiness score will appear here.",
            "Timeline/location/integrity/privacy/courtroom readiness.",
            210,
            1,
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
            2,
            1,
        ),
        (
            "OSINT + Image Content Reader",
            "ai_osint_content_view",
            "OSINT and deep image understanding will appear here.",
            "What appears inside the image, pixel/hidden leads, visual detail cues, sensitive pivots, and next actions.",
            240,
            3,
            0,
        ),
        (
            "AI Evidence Graph",
            "ai_graph_view",
            "AI evidence relationship graph will appear here.",
            "Relationship map across duplicates, devices, places, and AI links.",
            260,
            3,
            1,
        ),
        (
            "AI Contradiction Explainer",
            "ai_contradictions_view",
            "Contradiction explainer will appear here.",
            "Human-readable why-this-is-suspicious explanations.",
            220,
            4,
            0,
        ),
        (
            "AI Privacy Auditor",
            "ai_privacy_audit_view",
            "AI Privacy Auditor will appear here.",
            "Pre-export external sharing safety check.",
            200,
            4,
            1,
        ),
        (
            "Tesseract/OCR Startup Diagnostic",
            "ocr_diagnostic_view",
            "OCR/Tesseract diagnostic will appear here.",
            "Detects whether English/Arabic OCR is ready on the demo machine.",
            185,
            5,
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

    if hasattr(window, "ai_metric_evidence_value"):
        window.ai_metric_evidence_value.setText(str(len(records)))
        window.ai_metric_evidence_note.setText("Evidence items staged in the active isolated case.")

    if not records:
        if hasattr(window, "ai_metric_readiness_value"):
            window.ai_metric_readiness_value.setText("0%")
            window.ai_metric_readiness_note.setText("Load evidence to calculate readiness.")
            window.ai_metric_risk_value.setText("0")
            window.ai_metric_risk_note.setText("No high-risk evidence in queue yet.")
            window.ai_metric_privacy_value.setText("Awaiting")
            window.ai_metric_privacy_note.setText("Privacy export posture activates after analysis.")
            if hasattr(window, "ai_metric_image_value"):
                window.ai_metric_image_value.setText("SAFE")
                window.ai_metric_image_note.setText("No image danger judgement yet.")
        empty = "Load evidence to activate AI Guardian."
        for attr in [
            "ai_guardian_summary",
            "ai_readiness_view",
            "ai_image_triage_view",
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
        if hasattr(window, "ai_metric_readiness_value"):
            high = sum(1 for record in records if getattr(record, "risk_level", "Low") == "High" or getattr(record, "image_risk_is_dangerous", False))
            dangerous_images = sum(1 for record in records if getattr(record, "image_risk_is_dangerous", False))
            review_images = sum(1 for record in records if getattr(record, "image_risk_label", "SAFE") in {"MEDIUM", "HIGH", "CRITICAL"})
            image_scores = [int(getattr(record, "image_risk_score", 0) or 0) for record in records]
            max_image_score = max(image_scores or [0])
            max_image_record = max(records, key=lambda item: int(getattr(item, "image_risk_score", 0) or 0), default=None)
            max_image_label = str(getattr(max_image_record, "image_risk_label", "SAFE") if max_image_record else "SAFE")
            osint_sensitive = sum(1 for r in records if getattr(r, "osint_privacy_review", {}).get("records_with_sensitive_osint", 0))
            window.ai_metric_readiness_value.setText(f"{readiness.get('case_readiness', 0)}%")
            window.ai_metric_readiness_note.setText(readiness.get("summary", "Readiness unavailable.")[:72])
            window.ai_metric_risk_value.setText(str(high))
            window.ai_metric_risk_note.setText("Evidence items flagged High risk by scoring or AI review.")
            if hasattr(window, "ai_metric_image_value"):
                p0_images = sum(1 for record in records if str(_payload_value(record, "review_priority", "P3")) == "P0")
                p1_images = sum(1 for record in records if str(_payload_value(record, "review_priority", "P3")) == "P1")
                window.ai_metric_image_value.setText(f"{max_image_label} {max_image_score}%")
                window.ai_metric_image_note.setText(f"{dangerous_images} dangerous • P0 {p0_images} • P1 {p1_images} • review {review_images}")
            posture = "Redacted" if osint_sensitive or readiness.get("privacy_readiness", 0) < 100 else "Shareable"
            window.ai_metric_privacy_value.setText(posture)
            window.ai_metric_privacy_note.setText(privacy.get("summary", "Privacy audit unavailable.")[:72])

        if hasattr(window, "ai_guardian_summary"):
            window.ai_guardian_summary.setHtml(_render_guardian_summary_cards(records, readiness, custody_ok, privacy))
        if hasattr(window, "ai_image_triage_view"):
            window.ai_image_triage_view.setHtml(_render_image_triage_deck(records))
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
                if getattr(r, "osint_content_confidence", 0) > 0 or getattr(r, "osint_hypothesis_cards", []) or getattr(r, "image_risk_score", 0) > 0
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
