from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import Qt

try:
    from ...agents import AgentRequest
    from ...core.models import EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.agents import AgentRequest
    from app.core.models import EvidenceRecord


class ReviewSelectionMixin:

    def selected_records(self) -> List[EvidenceRecord]:
        selected: List[EvidenceRecord] = []
        for item in self.inventory_list.selectedItems():
            evidence_id = item.data(Qt.UserRole)
            record = self.case_manager.get_record(str(evidence_id)) if evidence_id else None
            if record is not None:
                selected.append(record)
        return selected

    def selected_record(self) -> Optional[EvidenceRecord]:
        item = self.inventory_list.currentItem()
        if item is None:
            return None
        evidence_id = item.data(Qt.UserRole)
        if not evidence_id:
            return None
        return self.case_manager.get_record(str(evidence_id))

    def clear_details(self, reason: str | None = None) -> None:
        self.current_preview_pixmap = None
        self.current_frames = []
        self.current_frame_index = 0
        self.current_frame_record = None
        message = reason or ("Select one evidence item from the left rail to begin review." if self.records else "This case has no evidence yet. Import files or a folder to begin the review.")
        self.image_preview.clear_source(message)
        self.metadata_overview.setPlainText("Select one evidence item to load its normalized metadata overview, verification posture, and anomaly explanation.")
        self.hidden_overview_view.setPlainText("Hidden-content scan results will appear here after you select an item.")
        self.hidden_code_view.setPlainText("Code-like markers, URLs, and context strings will appear here when detected. No item is selected yet.")
        self.review_audit_view.setPlainText("Select an evidence item to load its case-scoped audit activity.")
        if hasattr(self, "confidence_tree_view"):
            self.confidence_tree_view.setPlainText("Select one evidence item to explain what raised or lowered confidence.")
        self.metadata_view.clear()
        self.raw_exif_view.clear()
        self.normalized_shell.hide()
        self.raw_shell.hide()
        self.btn_toggle_normalized.setText("Show Normalized Dump")
        self.btn_toggle_raw.setText("Show Raw Tags")
        self.note_editor.clear()
        self.tags_editor.clear()
        self.bookmark_checkbox.setChecked(False)
        self.geo_text.setPlainText("No GPS selected yet. When an item is chosen, this page explains whether missing GPS is normal for its workflow.")
        if hasattr(self, "geo_reasoning_text"):
            self.geo_reasoning_text.setPlainText("Geo reasoning will appear here.")
        self.geo_leads_text.setPlainText("Location pivots and next-step suggestions will appear here.")
        self.timeline_text.setPlainText("Timeline analysis will appear here after you select evidence or load a case timeline.")
        if hasattr(self, "timeline_narrative"):
            self.timeline_narrative.setPlainText("Timeline narrative will appear here after the case produces at least one anchored item.")
        self.selection_verdict_view.setPlainText("Select an item to load a focused verdict narrative with courtroom-aware caveats.")
        if hasattr(self, "agent_insight_view"):
            self.agent_insight_view.setPlainText("AI review is ready. Select evidence to see the local agent plus batch AI risk context.")
        self.review_pivots_text.setPlainText("Choose evidence to see next pivots, compare candidates, and confirmation steps.")
        if hasattr(self, "review_tabs"):
            self.review_tabs.setCurrentIndex(0)
        self.preview_file_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText("—")  # type: ignore[attr-defined]
        if hasattr(self, "preview_hash_meta"):
            self.preview_hash_meta.value_label.setText("—")  # type: ignore[attr-defined]
        if hasattr(self, "preview_hash_aux_meta"):
            self.preview_hash_aux_meta.value_label.setText("—")  # type: ignore[attr-defined]
        if hasattr(self, "preview_stage_caption"):
            self.preview_stage_caption.setText(message)
        self.review_time_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.review_file_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.review_profile_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.score_ring.set_value(0)
        self.score_ring.set_caption("Evidence Score", "Awaiting selection")
        self.confidence_bar.setValue(0)
        self.confidence_bar_label.setText("Analytic confidence appears after selection")
        self.evidence_value_label.setText("Evidentiary value appears after selection")
        if hasattr(self, "courtroom_strength_label"):
            self.courtroom_strength_label.setText("Courtroom strength appears after selection")
        self.preview_zoom_pill.setText("Zoom 100%")
        self.frame_index_badge.setText("Frame 0/0")
        self.preview_state_badge.setText("Preview State: Awaiting selection")
        self.preview_parser_badge.setText("Parser: Awaiting selection")
        self.preview_signature_badge.setText("Signature: Awaiting selection")
        self.preview_trust_badge.setText("Trust: Awaiting selection")
        self._set_badge_defaults()
        self._set_geo_defaults()
        self._set_timeline_defaults()
        self._set_preview_controls(False)
        self._set_decision_selection_state(False)
        if hasattr(self, "summary_text"):
            self.summary_text.setPlainText(self._build_case_assessment_text())
        if hasattr(self, "dashboard_priority_text"):
            self.dashboard_priority_text.setPlainText(self._build_priority_text())


    def _set_preview_controls(self, enabled: bool) -> None:
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_prev_frame, self.btn_next_frame, self.btn_open_external, self.btn_fullscreen_preview, self.btn_export_from_review]:
            btn.setEnabled(enabled)
        animated = enabled and len(self.current_frames) > 1
        self.btn_prev_frame.setEnabled(animated)
        self.btn_next_frame.setEnabled(animated)

    def _set_decision_selection_state(self, has_selection: bool) -> None:
        self.decision_empty_hint.setVisible(not has_selection)
        self.decision_score_shell.setVisible(has_selection)
        self.decision_facts_shell.setVisible(has_selection)
        self.decision_breakdown_shell.setVisible(has_selection)

    def _set_badge_defaults(self) -> None:
        self.badge_source.setText("Source Profile: —")
        self.badge_time.setText("Time Anchor: —")
        self.badge_parser.setText("Parser / Trust: —")
        self.badge_signature.setText("Signature: —")
        self.badge_trust.setText("Trust: —")
        self.badge_gps.setText("GPS: —")
        self.badge_format.setText("Format: —")
        self.badge_risk.setText("Risk: —")
        self.score_auth_badge.setText("Authenticity 0")
        self.score_meta_badge.setText("Metadata 0")
        self.score_tech_badge.setText("Technical 0")
        self._apply_risk_badge_style(self.badge_risk, "Low")

    def _set_geo_defaults(self) -> None:
        self.geo_badge_status.setText("GPS State: —")
        self.geo_badge_coords.setText("Coordinates: —")
        self.geo_badge_altitude.setText("Altitude: —")
        self.geo_badge_map.setText("Map Package: —")
        self.geo_badge_detected_context.setText("Detected Map Context: —")
        self.geo_badge_possible_place.setText("Possible Place: —")
        self.geo_badge_map_confidence.setText("Map Confidence: —")
        if hasattr(self, "geo_badge_route"):
            self.geo_badge_route.setText("Route Overlay: —")
        if hasattr(self, "geo_map_context_view"):
            self.geo_map_context_view.setPlainText("Select evidence to load map context and OSINT AI location guidance.")
        if hasattr(self, "geo_metric_native_value"):
            self.geo_metric_native_value.setText("Awaiting")
            self.geo_metric_native_note.setText("Select evidence to inspect EXIF coordinates.")
            self.geo_metric_context_value.setText("Awaiting")
            self.geo_metric_context_note.setText("Map screenshots and OCR labels appear here.")
            self.geo_metric_place_value.setText("—")
            self.geo_metric_place_note.setText("No place candidate selected yet.")
            self.geo_metric_route_value.setText("—")
            self.geo_metric_route_note.setText("Route overlays and navigation context.")

    def _set_timeline_defaults(self) -> None:
        self.timeline_badge_start.setText("Earliest: —")
        self.timeline_badge_end.setText("Latest: —")
        self.timeline_badge_span.setText("Span: —")
        self.timeline_badge_order.setText("Ordering: —")

    def populate_details(self) -> None:
        record = self.selected_record()
        if record is None:
            self.clear_details()
            return

        self.note_editor.setPlainText(record.note or "")
        self.tags_editor.setText(record.tags or "")
        self.bookmark_checkbox.setChecked(record.bookmarked)
        self._prepare_frames(record)
        if self.current_frames:
            self.current_preview_pixmap = self.current_frames[self.current_frame_index]
            self.image_preview.set_source_pixmap(self.current_preview_pixmap)
            self._set_preview_controls(True)
        else:
            fallback = self._build_parser_fallback_text(record)
            self.current_preview_pixmap = None
            self.image_preview.clear_source(fallback)
            self._set_preview_controls(False)

        self.preview_file_meta.value_label.setText(f"{record.evidence_id} — {record.file_name}")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText(f"{record.source_type} • Value {record.evidentiary_label} {record.evidentiary_value} • Courtroom {record.courtroom_label} {record.courtroom_strength}")  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText(f"{record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText(f"Native {record.gps_display} • {record.gps_confidence}% | Derived {record.derived_geo_display} • {record.derived_geo_confidence}%")  # type: ignore[attr-defined]
        if hasattr(self, "preview_hash_meta"):
            self.preview_hash_meta.value_label.setText(self._short_hash(record.sha256, 16))  # type: ignore[attr-defined]
        if hasattr(self, "preview_hash_aux_meta"):
            self.preview_hash_aux_meta.value_label.setText(f"MD5 {self._short_hash(record.md5, 8)} • pHash {record.perceptual_hash}")  # type: ignore[attr-defined]
        if hasattr(self, "preview_stage_caption"):
            self.preview_stage_caption.setText(f"{record.file_name} • {record.dimensions} • {record.format_name} • parser {record.parser_status} • value {record.evidentiary_value}")
        self.review_time_shell.value_label.setText(f"{record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}% confidence)")  # type: ignore[attr-defined]
        self.review_file_shell.value_label.setText(f"{record.evidence_id} — {record.file_name}")  # type: ignore[attr-defined]
        self.review_profile_shell.value_label.setText(f"{record.source_type} • Triage {record.risk_level} {record.suspicion_score} • Courtroom {record.courtroom_label} {record.courtroom_strength}")  # type: ignore[attr-defined]
        self.preview_state_badge.setText(f"Preview State: {record.preview_status}")
        self.preview_parser_badge.setText(f"Parser: {record.parser_status}")
        self.preview_signature_badge.setText(f"Signature: {record.signature_status} • {record.format_signature}")
        self.preview_trust_badge.setText(f"Trust: {record.format_trust}")
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{max(1, len(self.current_frames))}")
        self.badge_source.setText(f"Source Profile: {record.source_type} • {record.source_profile_confidence}%")
        self.badge_time.setText(f"Time Anchor: {record.timestamp_source} • {record.timestamp_confidence}%")
        self.badge_parser.setText(f"Parser / Trust: {record.parser_status} • {record.format_trust}")
        self.badge_signature.setText(f"Signature: {record.signature_status}")
        self.badge_trust.setText(f"Trust: {record.format_trust}")
        self.badge_gps.setText(f"Native GPS: {'Recovered' if record.has_gps else 'Unavailable'} • {record.gps_confidence}% | Derived {record.derived_geo_confidence}%")
        self.badge_risk.setText(f"Risk: {record.risk_level} / Score {record.suspicion_score}")
        self.badge_format.setText(f"Format: {record.format_name} • {record.dimensions}")
        self.confidence_bar.setValue(record.confidence_score)
        self.confidence_bar_label.setText(f"Analytic confidence {record.confidence_score}%")
        self.evidence_value_label.setText(f"Evidentiary value {record.evidentiary_value}% • {record.evidentiary_label}")
        if hasattr(self, "courtroom_strength_label"):
            self.courtroom_strength_label.setText(f"Courtroom strength {record.courtroom_strength}% • {record.courtroom_label}")
        self.score_auth_badge.setText(f"Authenticity {record.authenticity_score}")
        self.score_meta_badge.setText(f"Metadata {record.metadata_score}")
        self.score_tech_badge.setText(f"Technical {record.technical_score}")
        self._apply_risk_badge_style(self.badge_risk, record.risk_level)
        self.geo_badge_status.setText(f"Geo State: {record.geo_status}")
        self.geo_badge_coords.setText(f"Native: {record.gps_display} | Derived: {record.derived_geo_display}")
        self.geo_badge_altitude.setText(f"Altitude: {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}")
        self.geo_badge_map.setText(f"Map Package: {'Ready' if self.current_map_path else 'Unavailable'}")
        self.geo_badge_detected_context.setText(f"Detected Map Context: {record.detected_map_context}")
        self.geo_badge_possible_place.setText(f"Possible Place: {record.possible_place}")
        self.geo_badge_map_confidence.setText(f"Map Confidence: {record.map_confidence}%")
        if hasattr(self, "geo_badge_route"):
            route_state = "Detected" if record.route_overlay_detected else "Not detected"
            self.geo_badge_route.setText(f"Route Overlay: {route_state} • {record.route_confidence}%")
        if hasattr(self, "geo_metric_native_value"):
            native_state = "Recovered" if record.has_gps else "Missing"
            self.geo_metric_native_value.setText(native_state)
            self.geo_metric_native_note.setText(f"{record.gps_display} • confidence {record.gps_confidence}%")
            context_state = getattr(record, "map_type", "Unknown") or record.detected_map_context or record.map_app_detected or "None"
            self.geo_metric_context_value.setText(str(context_state)[:28])
            self.geo_metric_context_note.setText(f"Readiness {getattr(record, 'map_answer_readiness_score', 0)}% • OCR {getattr(record, 'ocr_confidence', 0)}%")
            place = record.possible_place if record.possible_place not in {"", "Unavailable", "Unknown"} else (record.candidate_area if record.candidate_area != "Unavailable" else record.candidate_city)
            self.geo_metric_place_value.setText(str(place or "—")[:28])
            self.geo_metric_place_note.setText(getattr(record, "map_anchor_status", "No stable anchor"))
            self.geo_metric_route_value.setText(route_state)
            self.geo_metric_route_note.setText(f"Route confidence {record.route_confidence}% • {getattr(record, 'map_type', 'Unknown')}")
        self.score_ring.set_value(record.suspicion_score)
        self.score_ring.set_caption("Triage Score", record.risk_level)
        self.preview_zoom_pill.setText(f"Zoom {self.image_preview.zoom_percent()}%")
        self.summary_text.setPlainText(self._build_case_assessment_text())
        self.dashboard_priority_text.setPlainText(self._build_priority_text())
        self.review_pivots_text.setPlainText(self._build_summary_text(record))
        self.metadata_overview.setPlainText(self._build_metadata_overview_text(record))
        if hasattr(self, "acquisition_view"):
            self.acquisition_view.setPlainText(self._build_acquisition_text(record))
        if hasattr(self, "confidence_tree_view"):
            self.confidence_tree_view.setPlainText(self._build_confidence_tree_text(record))
        self.metadata_view.setPlainText(self._build_metadata_text(record))
        self.raw_exif_view.setPlainText(self._build_raw_exif_text(record))
        self.hidden_overview_view.setPlainText(self._build_hidden_content_text(record))
        self.hidden_code_view.setPlainText(self._build_hidden_content_dump(record))
        record.custody_event_summary = self.case_manager.db.summarize_evidence_events(record.case_id, record.evidence_id)
        self.review_audit_view.setPlainText(self._build_review_audit_text(record))
        self.geo_text.setPlainText(self._build_geo_text(record))
        if hasattr(self, "geo_reasoning_text"):
            self.geo_reasoning_text.setPlainText(self._build_geo_reasoning_text(record))
        if hasattr(self, "geo_map_context_view"):
            self.geo_map_context_view.setPlainText(self._build_geo_map_context_text(record))
        self.geo_leads_text.setPlainText(self._build_geo_leads_text(record))
        self.selection_verdict_view.setPlainText(self._build_verdict_panel_text(record))
        if hasattr(self, "agent_insight_view"):
            agent_response = self.agent.analyze_evidence(
                AgentRequest(
                    case_id=self.case_manager.active_case_id,
                    case_name=self.case_manager.active_case_name,
                    selected_record=record,
                    case_records=tuple(self.case_manager.records),
                    analyst_context=record.note or "",
                )
            )
            ai_context = (
                "\n\n---\nBatch AI Risk Engine\n"
                f"Provider: {record.ai_provider}\n"
                f"Risk label: {record.ai_risk_label} | Score delta: +{record.ai_score_delta} | Priority #{record.ai_priority_rank or '-'}\n"
                f"Flags: {', '.join(record.ai_flags) if record.ai_flags else 'None'}\n"
                f"Summary: {record.ai_summary}\n"
                f"Executive note: {record.ai_executive_note}\n\n"
                "AI action plan:\n" + "\n".join(f"- {item}" for item in (record.ai_action_plan or ["No AI action plan available."])) + "\n\n"
                "AI evidence matrix:\n" + "\n".join(f"- {item}" for item in (record.ai_corroboration_matrix or ["No AI matrix rows available."]))
            )
            self.agent_insight_view.setPlainText(agent_response.to_panel_text() + ai_context)
        self.review_pivots_text.setPlainText(self._build_summary_text(record))
        self._set_decision_selection_state(True)
        self._select_default_tab(record)
        self._highlight_selected_inventory_card()
