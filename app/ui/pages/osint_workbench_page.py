from __future__ import annotations

from datetime import datetime, timezone
import os
from html import escape
from typing import Any

from PyQt5.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ctf_geolocator_page import build_ctf_geolocator_page, refresh_ctf_geolocator_page
from ...core.osint.ctf_methodology import build_ctf_methodology


def _shell(window, title: str, attr: str, placeholder: str, subtitle: str, height: int) -> QWidget:
    view = window._make_guardian_view(placeholder, height)
    setattr(window, attr, view)
    return window._shell(title, view, subtitle)


def _metric_pill(window, label_text: str, value_attr: str, note_attr: str, value_text: str = "—", note_text: str = "Awaiting evidence") -> QFrame:
    frame = QFrame()
    frame.setObjectName("MetricPill")
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


def _records(window) -> list[Any]:
    return list(getattr(window.case_manager, "records", []) or [])


def _first_actionable_hypothesis(records: list[Any]) -> tuple[Any | None, dict[str, Any] | None]:
    for record in sorted(records, key=lambda item: (-int(getattr(item, "osint_content_confidence", 0) or 0), getattr(item, "evidence_id", ""))):
        for card in getattr(record, "osint_hypothesis_cards", []) or []:
            decision = card.get("analyst_decision", {}) or {}
            if decision.get("decision") in {None, "", "auto_generated", "needs_review"}:
                return record, card
    return None, None


def _update_top_decision(window, decision: str) -> None:
    records = _records(window)
    record, card = _first_actionable_hypothesis(records)
    if record is None or card is None:
        return
    note_map = {
        "verified": "Analyst marked the top OSINT lead as verified after review.",
        "rejected": "Analyst rejected the top OSINT lead as unsupported/noisy.",
        "needs_review": "Analyst reset the top OSINT lead to needs review.",
    }
    row = dict(card.get("analyst_decision", {}) or {})
    row.update(
        {
            "evidence_id": getattr(record, "evidence_id", ""),
            "hypothesis_id": card.get("hypothesis_id", "top-osint-hypothesis"),
            "decision": decision,
            "analyst_note": note_map.get(decision, "Analyst updated OSINT lead decision."),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    card["analyst_decision"] = row
    decisions = list(getattr(record, "osint_analyst_decisions", []) or [])
    decisions = [item for item in decisions if item.get("hypothesis_id") != row["hypothesis_id"]]
    decisions.append(row)
    record.osint_analyst_decisions = decisions
    if hasattr(window.case_manager, "_write_case_snapshot"):
        window.case_manager._write_case_snapshot()
    refresh_osint_workbench_page(window)
    if hasattr(window, "refresh_ai_guardian"):
        window.refresh_ai_guardian()


def _render_entity_graph(records: list[Any]) -> str:
    edges: list[str] = []
    for record in records:
        evidence_id = escape(str(getattr(record, "evidence_id", "EV")))
        entities = getattr(record, "osint_entities", []) or []
        for entity in entities[:8]:
            entity_type = escape(str(entity.get("entity_type", "entity")))
            value = escape(str(entity.get("value", ""))[:90])
            sensitivity = escape(str(entity.get("sensitivity", "normal")))
            edges.append(f"{evidence_id} → {entity_type}: {value} [{sensitivity}]")
    return "\n".join(edges[:80]) if edges else "No structured OSINT entities are available yet."


def _render_hypotheses(records: list[Any]) -> str:
    blocks: list[str] = []
    for record in records:
        evidence_id = escape(str(getattr(record, "evidence_id", "EV")))
        for card in (getattr(record, "osint_hypothesis_cards", []) or [])[:6]:
            title = escape(str(card.get("title", "OSINT hypothesis")))
            claim = escape(str(card.get("claim", "")))
            strength = escape(str(card.get("strength", "weak_signal")))
            confidence = escape(str(card.get("confidence", 0)))
            decision = card.get("analyst_decision", {}) or {}
            decision_text = escape(str(decision.get("decision", "needs_review")))
            basis = escape(", ".join(str(x) for x in card.get("basis", [])[:5]) or "not available")
            blocks.append(
                f"<div style='border:1px solid #2b4054;border-radius:12px;padding:10px;margin-bottom:9px;background:#0f1822;'>"
                f"<b>{evidence_id} • {title}</b><br/>"
                f"<span>{claim}</span><br/>"
                f"<span style='color:#9fb2c7;'>Strength: <b>{strength}</b> • Confidence: {confidence}% • Decision: <b>{decision_text}</b></span><br/>"
                f"<span style='color:#91a7bd;'>Basis: {basis}</span>"
                f"</div>"
            )
    return "".join(blocks) if blocks else "<p>No OSINT hypotheses have been generated yet.</p>"


def _render_privacy(records: list[Any]) -> str:
    lines: list[str] = []
    for record in records:
        review = getattr(record, "osint_privacy_review", {}) or {}
        if not review:
            continue
        lines.append(f"{record.evidence_id}: recommended={review.get('recommended_export_mode', 'unknown')} | sensitive={review.get('records_with_sensitive_osint', 0)}")
        for warning in review.get("warnings", [])[:3]:
            lines.append(f"  - {warning}")
    return "\n".join(lines) if lines else "No OSINT privacy review data is available yet."


def _selected_profiles(window) -> tuple[str, str]:
    region = getattr(getattr(window, "osint_region_combo", None), "currentText", lambda: "Region: Auto")()
    ocr_mode = getattr(getattr(window, "osint_ocr_mode_combo", None), "currentText", lambda: "OCR: current")()
    return region.replace("Region: ", "").strip(), ocr_mode.replace("OCR: ", "").strip()


def _apply_profile_settings(window) -> None:
    region, ocr_mode = _selected_profiles(window)
    os.environ["GEOTRACE_OSINT_REGION"] = region.lower().replace(" ", "_")
    if ocr_mode and ocr_mode != "current":
        os.environ["GEOTRACE_OCR_MODE"] = ocr_mode
    active_ocr = os.environ.get("GEOTRACE_OCR_MODE", "auto/current")
    message = f"Active next-scan profile: region={region}; OCR={active_ocr}. Existing records are not reprocessed until you rescan/import."
    setattr(window, "osint_active_region_profile", region)
    setattr(window, "osint_active_ocr_profile", active_ocr)
    if hasattr(window, "osint_profile_status"):
        window.osint_profile_status.setText(message)
    refresh_osint_workbench_page(window)


def build_osint_workbench_page(window) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    hero = QFrame()
    hero.setObjectName("PanelFrame")
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(16, 16, 16, 16)
    hero_layout.setSpacing(10)

    title = QLabel("Unified OSINT + CTF Investigation Lab")
    title.setObjectName("SectionLabel")
    meta = QLabel(
        "One workspace for OSINT review and CTF-style image solving: hypotheses, entity graph, OCR/region profile, "
        "pixel/hidden-content leads, hacker methodology, candidate ranking, answer support, and privacy-gated pivots."
    )
    meta.setObjectName("SectionMetaLabel")
    meta.setWordWrap(True)
    hero_layout.addWidget(title)
    hero_layout.addWidget(meta)

    metrics = QHBoxLayout()
    metrics.setSpacing(10)
    metrics.addWidget(_metric_pill(window, "Evidence", "osint_metric_evidence_value", "osint_metric_evidence_note", "0", "No evidence loaded yet."))
    metrics.addWidget(_metric_pill(window, "Top Lead", "osint_metric_lead_value", "osint_metric_lead_note", "—", "Best hypothesis confidence."))
    metrics.addWidget(_metric_pill(window, "OCR Ready", "osint_metric_ocr_value", "osint_metric_ocr_note", "0", "Records with OCR or map labels."))
    metrics.addWidget(_metric_pill(window, "Active Candidates", "osint_metric_candidates_value", "osint_metric_candidates_note", "0", "CTF/geo candidates awaiting review."))
    metrics.addWidget(_metric_pill(window, "Hidden Content", "osint_metric_hidden_value", "osint_metric_hidden_note", "0", "Pixel/alpha/LSB review flags."))
    hero_layout.addLayout(metrics)

    controls = QHBoxLayout()
    controls.setSpacing(8)
    window.osint_region_combo = QComboBox()
    window.osint_region_combo.addItems(["Region: Auto", "Region: Egypt", "Region: Middle East", "Region: Global"])
    window.osint_ocr_mode_combo = QComboBox()
    window.osint_ocr_mode_combo.addItems(["OCR: current", "OCR: off", "OCR: quick", "OCR: deep", "OCR: map_deep"])
    window.btn_osint_apply_profile = QPushButton("Apply for Next Scan")
    window.btn_osint_apply_profile.clicked.connect(lambda: _apply_profile_settings(window))
    window.btn_osint_refresh = QPushButton("Refresh Workbench")
    window.btn_osint_refresh.clicked.connect(lambda: refresh_osint_workbench_page(window))
    window.btn_osint_verify_top = QPushButton("Verify Top Lead")
    window.btn_osint_verify_top.clicked.connect(lambda: _update_top_decision(window, "verified"))
    window.btn_osint_reject_top = QPushButton("Reject Top Lead")
    window.btn_osint_reject_top.clicked.connect(lambda: _update_top_decision(window, "rejected"))
    window.btn_osint_reset_top = QPushButton("Reset to Review")
    window.btn_osint_reset_top.clicked.connect(lambda: _update_top_decision(window, "needs_review"))
    for item in [
        window.osint_region_combo,
        window.osint_ocr_mode_combo,
        window.btn_osint_apply_profile,
        window.btn_osint_refresh,
        window.btn_osint_verify_top,
        window.btn_osint_reject_top,
        window.btn_osint_reset_top,
    ]:
        controls.addWidget(item)
    controls.addStretch(1)
    hero_layout.addLayout(controls)
    window.osint_profile_status = QLabel("Active next-scan profile: region=Auto; OCR=auto/current. Apply a profile to affect future imports or rescans.")
    window.osint_profile_status.setObjectName("SectionMetaLabel")
    window.osint_profile_status.setWordWrap(True)
    hero_layout.addWidget(window.osint_profile_status)
    layout.addWidget(hero)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(14)
    grid.addWidget(_shell(window, "Hypothesis Cards", "osint_hypothesis_view", "OSINT hypotheses will appear here.", "Accept/reject workflow keeps leads separate from proof.", 320), 0, 0)
    grid.addWidget(_shell(window, "Entity Graph", "osint_entity_graph_view", "OSINT entity graph will appear here.", "Pivots extracted from OCR/map URLs/place labels.", 260), 0, 1)
    grid.addWidget(_shell(window, "Evidence Strength", "osint_strength_view", "Evidence strength summary will appear here.", "proof / lead / weak_signal language for each item.", 220), 1, 0)
    grid.addWidget(_shell(window, "OCR + Region Profile", "osint_ocr_region_view", "OCR and region-aware details will appear here.", "OCR mode, region hits, map labels, and confidence.", 220), 1, 1)
    grid.addWidget(_shell(window, "Privacy Review", "osint_privacy_review_view", "OSINT privacy review will appear here.", "Pre-export warning layer for sensitive pivots.", 220), 2, 0)
    grid.addWidget(_shell(window, "CTF/Hacker Summary", "osint_ctf_summary_view", "CTF/Hacker summary will appear here.", "Readiness, source hierarchy, solvability, filename-vs-OCR/GPS separation.", 220), 2, 1)
    grid.addWidget(_shell(window, "Deep Image Intelligence", "osint_image_detail_view", "Image detail intelligence will appear here.", "Layout, object-like cues, quality flags, alpha/hidden-content review hints.", 240), 3, 0, 1, 2)
    grid.addWidget(_shell(window, "Export Appendix Preview", "osint_export_appendix_view", "OSINT appendix preview will appear here.", "What the report package should include or redact.", 220), 4, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    layout.addLayout(grid)

    layout.addWidget(build_ctf_geolocator_page(window, embedded=True))
    layout.addStretch(1)
    return widget


def refresh_osint_workbench_page(window) -> None:
    records = _records(window)
    if hasattr(window, "osint_metric_evidence_value"):
        hypotheses = [card for record in records for card in (getattr(record, "osint_hypothesis_cards", []) or []) if isinstance(card, dict)]
        candidate_rows = [candidate for record in records for candidate in (getattr(record, "geo_candidates", []) or []) if isinstance(candidate, dict)]
        active_candidates = [candidate for candidate in candidate_rows if candidate.get("status", "needs_review") != "rejected"]
        hidden_hits = [
            record
            for record in records
            if int(getattr(record, "pixel_hidden_score", 0) or 0) >= 15
            or bool(getattr(record, "pixel_lsb_strings", []) or [])
            or bool(getattr(record, "alpha_channel_notes", []) or [])
        ]
        ocr_ready = [
            record
            for record in records
            if int(getattr(record, "ocr_confidence", 0) or 0) > 0
            or bool(getattr(record, "ocr_map_labels", []) or [])
        ]
        top_confidence = 0
        top_title = "No hypothesis yet"
        for card in hypotheses:
            confidence = int(card.get("confidence", 0) or 0)
            if confidence >= top_confidence:
                top_confidence = confidence
                top_title = str(card.get("title", "OSINT hypothesis"))[:48]
        window.osint_metric_evidence_value.setText(str(len(records)))
        window.osint_metric_evidence_note.setText("Evidence items analysed in the active case.")
        window.osint_metric_lead_value.setText(f"{top_confidence}%")
        window.osint_metric_lead_note.setText(top_title if hypotheses else "Generate or import evidence to build leads.")
        window.osint_metric_ocr_value.setText(str(len(ocr_ready)))
        window.osint_metric_ocr_note.setText("Records with OCR confidence or extracted labels.")
        window.osint_metric_candidates_value.setText(str(len(active_candidates)))
        window.osint_metric_candidates_note.setText(f"{len(candidate_rows)} total candidate rows across the workbench.")
        window.osint_metric_hidden_value.setText(str(len(hidden_hits)))
        window.osint_metric_hidden_note.setText("Potential hidden-content or pixel-level review hits.")
    if hasattr(window, "osint_hypothesis_view"):
        window.osint_hypothesis_view.setHtml(_render_hypotheses(records))
    if hasattr(window, "osint_entity_graph_view"):
        window.osint_entity_graph_view.setPlainText(_render_entity_graph(records))
    if hasattr(window, "osint_strength_view"):
        lines = []
        for record in records[:30]:
            lines.append(
                f"{record.evidence_id}: evidence={getattr(record, 'evidence_strength_label', 'weak_signal')} "
                f"({getattr(record, 'evidence_strength_score', 0)}%) | map={getattr(record, 'map_evidence_strength', 'weak_signal')} "
                f"| location={getattr(record, 'derived_geo_display', 'Unavailable')}"
            )
        window.osint_strength_view.setPlainText("\n".join(lines) if lines else "Load evidence to generate evidence-strength rows.")
    if hasattr(window, "osint_ocr_region_view"):
        selected_region, selected_ocr_profile = _selected_profiles(window)
        active_region = getattr(window, "osint_active_region_profile", os.environ.get("GEOTRACE_OSINT_REGION", selected_region))
        active_ocr = getattr(window, "osint_active_ocr_profile", os.environ.get("GEOTRACE_OCR_MODE", selected_ocr_profile))
        region = str(active_region).replace("_", " ").title() if str(active_region).islower() else str(active_region)
        ocr_profile = str(active_ocr)
        lines = [f"Active next-scan profile: region={region}; OCR={ocr_profile}", f"Selected controls: region={selected_region}; OCR={selected_ocr_profile}", ""]
        for record in records[:20]:
            regions = getattr(record, "ocr_region_signals", []) or []
            compact = []
            for item in regions[:3]:
                if isinstance(item, dict):
                    compact.append(f"{item.get('region', 'region')}:{item.get('weight', 0)}%:{', '.join(item.get('place_hits', [])[:2]) or 'text'}")
            lines.append(
                f"{record.evidence_id}: OCR {getattr(record, 'ocr_confidence', 0)}% | labels={', '.join(getattr(record, 'ocr_map_labels', [])[:3]) or 'none'} | regions={' | '.join(compact) or 'none'}"
            )
        window.osint_ocr_region_view.setPlainText("\n".join(lines) if lines else "No OCR/region profile yet.")
    if hasattr(window, "osint_privacy_review_view"):
        window.osint_privacy_review_view.setPlainText(_render_privacy(records))
    if hasattr(window, "osint_image_detail_view"):
        lines = []
        for record in records[:30]:
            lines.append(
                f"{record.evidence_id}: {getattr(record, 'image_detail_label', 'Unavailable')} "
                f"({getattr(record, 'image_detail_confidence', 0)}%) | "
                f"layout={', '.join(getattr(record, 'image_layout_hints', [])[:3]) or 'none'} | "
                f"objects={', '.join(getattr(record, 'image_object_hints', [])[:3]) or 'none'}"
            )
            metrics = dict(getattr(record, 'image_detail_metrics', {}) or {})
            if metrics:
                lines.append(
                    "  strategy: "
                    + str(metrics.get('analysis_strategy', 'balanced visual review'))
                    + f" | OCR={metrics.get('ocr_priority_score', 0)}"
                    + f" map={metrics.get('map_review_priority_score', 0)}"
                    + f" geo={metrics.get('geolocation_potential_score', 0)}"
                    + f" hidden={metrics.get('hidden_content_priority_score', 0)}"
                    + f" gate={metrics.get('quality_gate', 'ready_for_triage')}"
                )
                lines.append("  target: " + str(metrics.get('corroboration_target', 'baseline packet')))
            quality = getattr(record, 'image_quality_flags', []) or []
            if quality:
                lines.append("  quality: " + " | ".join(str(x) for x in quality[:3]))
            pixel = getattr(record, 'pixel_hidden_verdict', 'Not evaluated')
            pixel_score = getattr(record, 'pixel_hidden_score', 0)
            lines.append(f"  hidden pixels: {pixel} ({pixel_score}%)")
        window.osint_image_detail_view.setPlainText("\n".join(lines) if lines else "No image-detail intelligence generated yet.")
    if hasattr(window, "osint_ctf_summary_view"):
        lines = []
        for record in records[:30]:
            candidates = [c for c in (getattr(record, 'geo_candidates', []) or []) if isinstance(c, dict)]
            active_candidates = [c for c in candidates if c.get('status', 'needs_review') != 'rejected']
            methodology = build_ctf_methodology(record)
            lines.append(
                f"{record.evidence_id}: readiness={methodology.get('readiness_label', 'Recon only')} "
                f"({methodology.get('readiness_score', 0)}%) | "
                f"solvability={getattr(record, 'location_solvability_score', 0)}% "
                f"({getattr(record, 'location_solvability_label', 'No useful geo clue')}) | "
                f"active_candidates={len(active_candidates)} / total={len(candidates)} | "
                f"source_families={len([x for x in methodology.get('source_families', []) if x != 'filename_hint'])} | "
                f"filename_hints={', '.join(getattr(record, 'filename_location_hints', [])[:3]) or 'none'}"
            )
            blockers = methodology.get('blockers', []) or []
            if blockers:
                lines.extend(f"  blocker: {item}" for item in blockers[:2])
            ladder = getattr(record, 'map_evidence_ladder', []) or []
            if ladder:
                lines.extend(f"  - {item}" for item in ladder[:4])
        window.osint_ctf_summary_view.setPlainText("\n".join(lines) if lines else "No CTF GeoLocator rows yet.")
    if hasattr(window, "osint_export_appendix_view"):
        count_h = sum(len(getattr(r, "osint_hypothesis_cards", []) or []) for r in records)
        count_e = sum(len(getattr(r, "osint_entities", []) or []) for r in records)
        sensitive = sum(1 for r in records if (getattr(r, "osint_privacy_review", {}) or {}).get("records_with_sensitive_osint", 0))
        window.osint_export_appendix_view.setPlainText(
            "OSINT appendix preview\n"
            f"- Hypothesis cards: {count_h}\n"
            f"- Entity pivots: {count_e}\n"
            f"- Sensitive OSINT records: {sensitive}\n"
            "- Recommended external mode: Shareable/Courtroom redacted unless the recipient is authorised for location pivots."
        )
    if hasattr(window, "ctf_clue_cards_view"):
        refresh_ctf_geolocator_page(window)
