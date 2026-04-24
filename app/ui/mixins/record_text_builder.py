from __future__ import annotations

from pathlib import Path

try:
    from ...core.models import EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.models import EvidenceRecord


class RecordTextBuilderMixin:
    """Pure-ish text builders used by the review, geo, audit, and report panes.

    Keeping these narrative builders outside ``GeoTraceMainWindow`` makes the
    main window easier to scan and gives future AI-agent summaries a clean
    surface to call or replace without touching the UI wiring.
    """

    def _short_hash(self, value: str, width: int = 14) -> str:
        value = value or ""
        if len(value) <= width * 2:
            return value
        return f"{value[:width]}…{value[-width:]}"

    def _build_acquisition_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"Imported: {record.imported_at}",
            f"Origin: {Path(record.file_path).name}",
            f"SHA-256: {self._short_hash(record.sha256, 16)}",
            f"MD5 / pHash: {self._short_hash(record.md5, 8)} • {record.perceptual_hash}",
            f"Parser / Trust: {record.parser_status} / {record.format_trust}",
            f"Courtroom strength: {record.courtroom_strength}% ({record.courtroom_label})",
        ]
        if record.custody_event_summary:
            lines.extend(["", "Recent events:"])
            lines.extend(f"- {item}" for item in record.custody_event_summary[:3])
        return "\n".join(lines)

    def _build_geo_reasoning_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"Geo posture: {record.geo_status}",
            f"Native: {record.gps_display} ({record.gps_confidence}%)",
            f"Derived: {record.derived_geo_display} ({record.derived_geo_confidence}%)",
        ]
        if record.has_gps:
            lines.extend(["", "Direct map anchor is available.", "Validate place claims against venue context and the time anchor."])
        elif record.derived_geo_display != "Unavailable":
            lines.extend(["", "Only screenshot-derived geo clues were found.", "Treat them as weak leads until OCR, URLs, or map labels corroborate them."])
        elif record.ocr_map_labels or record.possible_geo_clues:
            labels = record.possible_geo_clues or record.ocr_map_labels
            lines.extend([
                "",
                "Map/place text exists, but no stable coordinates were parsed.",
                f"Top visible lead: {labels[0] if labels else 'none'}",
                "Use deep OCR, original map/share link, browser history, or source app context before making a location claim.",
            ])
        else:
            lines.extend(["", "No native or derived geo clue was recovered.", "Use timeline, source profile, filename, and custody context instead."])
        return "\n".join(lines)

    def _build_confidence_tree_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"Triage score: {record.suspicion_score} • Risk: {record.risk_level}",
            f"Primary issue: {record.score_primary_issue}",
            f"Why: {record.score_reason}",
            f"Next step: {record.score_next_step}",
            "",
            f"├─ Analytic confidence: {record.confidence_score}%",
            f"├─ Evidentiary value: {record.evidentiary_value}% ({record.evidentiary_label})",
            f"└─ Courtroom strength: {record.courtroom_strength}% ({record.courtroom_label})",
            "",
            "Top contributors:",
        ]
        contributors = record.anomaly_contributors[:4] if record.anomaly_contributors else []
        if contributors:
            lines.extend(f"• {item}" for item in contributors)
        else:
            lines.append("• No strong anomaly contributor was recorded.")
        lines.extend([
            "",
            f"AI-assisted review: {record.ai_risk_label} (delta +{record.ai_score_delta}, priority #{record.ai_priority_rank or '-'})",
            f"AI summary: {record.ai_summary}",
            f"AI executive note: {record.ai_executive_note}",
            f"AI next best action: {record.ai_next_best_action}",
            f"AI courtroom readiness: {record.ai_courtroom_readiness.replace(chr(10), ' | ')}",
        ])
        if record.ai_flags:
            lines.append("AI flags: " + ", ".join(record.ai_flags))
        if record.ai_action_plan:
            lines.extend(["", "AI action plan:"])
            lines.extend(f"• {item}" for item in record.ai_action_plan[:5])
        if record.validation_hits or record.validation_misses:
            lines.extend([
                "",
                f"Validation hits: {len(record.validation_hits)} • misses: {len(record.validation_misses)}",
            ])
            if record.validation_misses:
                lines.append(f"Validation focus: {record.validation_misses[0]}")
        lines.extend([
            "",
            "Reading guide:",
            "• Primary issue = the top reason this file deserves attention.",
            "• Confidence = stability of the analytic reading.",
            "• Value = usefulness for time, place, origin, or linkage.",
            "• Courtroom = how conservative the posture should remain.",
        ])
        return "\n".join(lines)


    def _build_metadata_overview_text(self, record: EvidenceRecord) -> str:
        ocr_line = record.visible_text_excerpt or "No strong OCR clue recovered."
        lead_issue = record.metadata_issues[0] if record.metadata_issues else record.metadata_issue_summary
        strength = record.metadata_strengths[0] if record.metadata_strengths else "No strong metadata strength was captured yet."
        recommendation = record.metadata_recommendations[0] if record.metadata_recommendations else record.score_next_step
        lines = [
            f"Parser: {record.parser_status} • Trust: {record.format_trust} • Signature: {record.signature_status}",
            f"Main metadata issue: {lead_issue}",
            f"Best strength: {strength}",
            f"Action: {recommendation}",
            f"Dimensions: {record.dimensions} • Frames: {record.frame_count} • Source: {record.source_type} ({record.source_profile_confidence}%)",
            f"Time: {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
            f"Native GPS: {record.gps_display} • Derived: {record.derived_geo_display}",
            f"OCR clue: {ocr_line}",
            f"Hashes: SHA-256 {self._short_hash(record.sha256, 14)} • MD5 {self._short_hash(record.md5, 8)}",
        ]
        return "\n".join(lines)


    def _build_summary_text(self, record: EvidenceRecord) -> str:
        if record.parser_status != "Valid":
            return (
                f"{record.evidence_id} needs a fallback workflow.\n\n"
                f"Lead: {record.parse_error or 'Parser review required.'}\n\n"
                "Next actions: preserve hashes, validate the signature with a second parser, and avoid content claims until structure is confirmed."
            )
        if record.has_gps:
            return (
                f"{record.evidence_id} has native GPS and strong map value.\n\n"
                f"Anchor: {record.timestamp} via {record.timestamp_source}. Coordinate: {record.gps_display}.\n\n"
                "Next actions: verify the place externally, compare nearby evidence, and confirm the time with logs or witnesses."
            )
        if record.duplicate_group:
            return (
                f"{record.evidence_id} sits inside {record.duplicate_group}.\n\n"
                "Next actions: compare dimensions, timestamps, and software/device tags to separate original from derivative media."
            )
        return (
            f"{record.evidence_id} is mainly a timeline/source anchor.\n\n"
            f"Value: {record.evidentiary_label} {record.evidentiary_value}% • Confidence: {record.confidence_score}%.\n\n"
            "Next actions: validate the time anchor, preserve custody notes, and correlate the item with adjacent case events."
        )

    def _build_metadata_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ NORMALIZED METADATA ]",
            "=" * 96,
            f"Case ID                : {record.case_id}",
            f"Evidence ID            : {record.evidence_id}",
            f"Original File Path     : {record.original_file_path}",
            f"Working Copy Path      : {record.working_copy_path}",
            f"File Size              : {record.file_size:,} bytes",
            f"Format                 : {record.format_name}",
            f"Signature Status       : {record.signature_status}",
            f"Format Signature       : {record.format_signature}",
            f"Container Trust        : {record.format_trust}",
            f"Parser Status          : {record.parser_status}",
            f"Structure Status       : {record.structure_status}",
            f"Preview Status         : {record.preview_status}",
            f"Dimensions             : {record.dimensions}",
            f"Megapixels             : {record.megapixels:.2f}",
            f"Aspect Ratio           : {record.aspect_ratio}",
            f"Brightness Mean        : {record.brightness_mean:.2f}",
            f"Color Mode             : {record.color_mode}",
            f"Alpha Channel          : {'Yes' if record.has_alpha else 'No'}",
            f"DPI                    : {record.dpi}",
            f"Timestamp              : {record.timestamp}",
            f"Timestamp Source       : {record.timestamp_source}",
            f"Timestamp Confidence   : {record.timestamp_confidence}%",
            f"Timestamp Verdict      : {record.timestamp_verdict}",
            f"Filesystem Birth/Created: {record.created_time}",
            f"Birth-Time Note        : {record.created_time_note}",
            f"Filesystem Modified    : {record.modified_time}",
            f"Source Type            : {record.source_type}",
            f"Source Subtype         : {record.source_subtype}",
            f"Source Confidence      : {record.source_profile_confidence}%",
            f"Environment Profile    : {record.environment_profile}",
            f"Application Detected   : {record.app_detected}",
            f"OCR Confidence         : {record.ocr_confidence}%",
            f"OCR note             : {record.ocr_note}",
            f"Camera / Device        : {record.device_model}",
            f"Camera Make            : {record.camera_make}",
            f"Software               : {record.software}",
            f"Native GPS             : {record.gps_display}",
            f"Derived Geo            : {record.derived_geo_display}",
            f"Derived Geo Source     : {record.derived_geo_source}",
            f"Possible Geo Clues     : {', '.join(record.possible_geo_clues) if record.possible_geo_clues else 'None'}",
            f"GPS Altitude           : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"SHA-256                : {record.sha256}",
            f"MD5                    : {record.md5}",
            f"Perceptual Hash        : {record.perceptual_hash}",
            f"Duplicate Cluster      : {record.duplicate_group or 'None'}",
            f"Duplicate Relation     : {record.duplicate_relation or 'None'}",
            f"Duplicate Method       : {record.duplicate_method or 'None'}",
            f"Duplicate Peers        : {', '.join(record.duplicate_peers) if record.duplicate_peers else 'None'}",
            f"Scene Group            : {record.scene_group or 'None'}",
            f"Similarity Note        : {record.similarity_note}",
            f"Frames / Animation     : {record.frame_count} / {'Animated' if record.is_animated else 'Static'}",
            f"Animation Duration     : {record.animation_duration_ms if record.animation_duration_ms else 'N/A'}",
            f"Integrity              : {record.integrity_status}",
            f"Integrity Note         : {record.integrity_note}",
            f"Tags                   : {record.tags or 'None'}",
            f"Bookmarked             : {'Yes' if record.bookmarked else 'No'}",
            "",
            "[ EXPLAINABILITY ]",
            "-" * 96,
            f"Primary issue          : {record.score_primary_issue}",
            f"Why it matters         : {record.score_reason}",
            f"Recommended next step  : {record.score_next_step}",
            f"Metadata summary       : {record.metadata_issue_summary}",
            f"AI provider            : {record.ai_provider}",
            f"AI risk label          : {record.ai_risk_label}",
            f"AI score delta         : +{record.ai_score_delta}",
            f"AI priority rank       : #{record.ai_priority_rank or '-'}",
            f"AI flags               : {', '.join(record.ai_flags) if record.ai_flags else 'None'}",
            f"AI executive note      : {record.ai_executive_note}",
            f"AI next best action    : {record.ai_next_best_action}",
            f"AI courtroom readiness : {record.ai_courtroom_readiness.replace(chr(10), ' | ')}",
            f"AI summary             : {record.ai_summary}",
            "",
            "Metadata issues:",
        ]
        lines.extend([f"- {item}" for item in (record.metadata_issues or ["No dominant metadata issue recorded."])])
        lines.extend(["", "Metadata strengths:"])
        lines.extend([f"- {item}" for item in (record.metadata_strengths or ["No major metadata strength recorded."])])
        lines.extend(["", "Recommendations:"])
        lines.extend([f"- {item}" for item in (record.metadata_recommendations or [record.score_next_step])])
        lines.extend(["", "[ SCORE BREAKDOWN ]", "-" * 96])
        lines.extend(record.score_breakdown or ["No score breakdown available."])
        if record.ai_action_plan:
            lines.extend(["", "[ AI ACTION PLAN ]", "-" * 96])
            lines.extend([f"- {item}" for item in record.ai_action_plan])
        if record.ai_corroboration_matrix:
            lines.extend(["", "[ AI CORROBORATION MATRIX ]", "-" * 96])
            lines.extend([f"- {item}" for item in record.ai_corroboration_matrix])
        if record.ai_case_links:
            lines.extend(["", "[ AI CASE LINKS ]", "-" * 96])
            lines.extend([f"- {item}" for item in record.ai_case_links])
        if record.ai_breakdown:
            lines.extend(["", "[ AI-ASSISTED BATCH REVIEW ]", "-" * 96])
            lines.extend(record.ai_breakdown)
        if record.validation_hits or record.validation_misses:
            lines.extend(["", "[ VALIDATION AGAINST GROUND TRUTH ]", "-" * 96])
            lines.extend([f"PASS: {item}" for item in record.validation_hits] or ["PASS: none recorded"])
            lines.extend([f"MISS: {item}" for item in record.validation_misses] or ["MISS: none recorded"])
        if record.parse_error:
            lines.extend(["", "[ PARSER DIAGNOSTICS ]", "-" * 96, record.parse_error])
        return "\n".join(lines)


    def _build_raw_exif_text(self, record: EvidenceRecord) -> str:
        lines = ["[ RAW EXIF / EMBEDDED TAGS ]", "=" * 96]
        if not record.raw_exif:
            lines.append("No raw EXIF tags were recovered from the selected file.")
            return "\n".join(lines)
        for key, value in sorted(record.raw_exif.items()):
            lines.append(f"{key:<34}: {value}")
        return "\n".join(lines)

    def _build_geo_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ GEO INTELLIGENCE ]",
            "=" * 96,
            f"Evidence ID           : {record.evidence_id}",
            f"Native Coordinates    : {record.gps_display}",
            f"GPS Source            : {record.gps_source}",
            f"GPS Confidence        : {record.gps_confidence}%",
            f"Derived Geo           : {record.derived_geo_display}",
            f"Derived Geo Source    : {record.derived_geo_source}",
            f"Derived Geo Confidence: {record.derived_geo_confidence}%",
            f"Altitude              : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"Map Package           : {'Available' if self.current_map_path else 'Not generated'}",
            f"Time Anchor           : {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
            f"Source Profile        : {record.source_type} / {record.source_subtype}",
            f"Parser / Signature    : {record.parser_status} / {record.signature_status}",
            "",
            f"Primary GPS posture   : {record.gps_primary_issue}",
            f"Verification note     : {record.gps_verification}",
            f"Possible geo clues    : {', '.join(record.possible_geo_clues[:4]) if record.possible_geo_clues else 'None'}",
            f"OCR map labels        : {', '.join(record.ocr_map_labels[:5]) if record.ocr_map_labels else 'None'}",
            f"Source reasons        : {'; '.join(record.source_profile_reasons[:2]) if record.source_profile_reasons else 'None'}",
            "",
            "[ GPS VERIFICATION LADDER ]",
            "-" * 96,
        ]
        lines.extend(record.gps_ladder or ["No GPS verification ladder generated."])
        lines.extend(["", "Interpretation:"])
        if record.has_gps:
            lines.extend(
                [
                    "Native GPS is present, so map-based reconstruction should be prioritized.",
                    "Next pivots: validate venue, route plausibility, travel timing, and any nearby corroborating uploads.",
                ]
            )
        elif record.derived_geo_display != "Unavailable":
            lines.extend(
                [
                    "No native GPS was recovered, but screenshot-derived location clues were parsed from visible content.",
                    "Why this matters: derived geo is weaker than EXIF GPS, but it can still guide map correlation and external validation.",
                    "Next pivots: preserve visible URLs, browser/app context, timeline anchors, and any saved/shared map links.",
                ]
            )
        elif record.ocr_map_labels or record.possible_geo_clues:
            lines.extend(
                [
                    "No native GPS or stable coordinates were recovered, but OCR/map text produced possible place leads.",
                    "Why this matters: map labels can guide OSINT and source-app corroboration, but they are weaker than EXIF GPS.",
                    "Next pivots: deep OCR with Arabic enabled, original map/share URL, browser history, source app context, and witness timeline.",
                ]
            )
        else:
            lines.extend(
                [
                    "No native GPS was recovered from the file.",
                    "Why this can still be normal: screenshots, messaging exports, edited graphics, and malformed assets often lack native GPS.",
                    "Next pivots: timeline anchor, source profile, device continuity, filenames, chat context, and custody notes.",
                ]
            )
        if record.parser_status != "Valid":
            lines.extend(["", "Structure warning: decoder failed, so geolocation conclusions must rely on external evidence rather than preview content."])
        return "\n".join(lines)


    def _build_geo_leads_text(self, record: EvidenceRecord) -> str:
        if record.has_gps:
            leads = record.osint_leads[:]
        elif record.derived_geo_display != "Unavailable":
            leads = record.osint_leads[:] + [
                "Derived geo is present even though native GPS is absent; preserve browser/app origin and any shared map link.",
                "Explain clearly that the location clue is screenshot-derived, not EXIF-native.",
            ]
        elif record.ocr_map_labels or record.possible_geo_clues:
            labels = record.possible_geo_clues or record.ocr_map_labels
            leads = record.osint_leads[:] + [
                "Possible map/place text exists without coordinates; treat it as a venue lead only.",
                f"Review visible label manually: {labels[0] if labels else 'None'}.",
                "Run deep OCR with Arabic enabled or obtain the original Google Maps/share link before making a location claim.",
            ]
        else:
            leads = record.osint_leads[:] + [
                "No native GPS → explain absence using workflow profile before framing it as suspicious.",
                "Correlate timestamp anchor with uploads, messages, or witness timeline.",
            ]
        lines = ["[ NEXT PIVOTS ]", "=" * 96]
        lines.extend(f"- {lead}" for lead in leads)
        return "\n".join(lines)


    def _build_case_assessment_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Load evidence to generate a case-wide assessment. Case isolation is already active, so future custody logs will stay scoped to this case only."
        total = len(records)
        gps = sum(1 for r in records if r.has_gps)
        high = sum(1 for r in records if r.risk_level == "High")
        duplicates = len({r.duplicate_group for r in records if r.duplicate_group})
        parser_issues = sum(1 for r in records if r.parser_status != "Valid" or r.signature_status == "Mismatch")
        dominant_source = max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
        return (
            f"Total evidence items: {total}\n\n"
            f"Dominant source profile: {dominant_source}\n\n"
            f"GPS-bearing media: {gps} | Duplicate clusters: {duplicates}\n\n"
            f"Priority review items: {high} high-risk | Parser/signature alerts: {parser_issues}\n\n"
            "Interpretation: the active case summary is computed only from the current isolated case, so previous sessions do not contaminate the dashboard."
        )

    def _build_priority_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Case priorities will appear here after evidence is loaded."
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))[:5]
        lines = []
        for idx, record in enumerate(ordered, start=1):
            why = record.anomaly_reasons[0] if record.anomaly_reasons else "No explicit anomaly note."
            lines.append(
                f"{idx}. {record.evidence_id} — {record.risk_level} / Score {record.suspicion_score} / {record.source_type}\n"
                f"   Parser: {record.parser_status} • Signature: {record.signature_status} • Trust: {record.format_trust}\n"
                f"   Why it matters: {why}"
            )
        lines.extend([
            "",
            "Recommended next steps:",
            "Validate time anchors against chats, uploads, or witness timelines.",
            "Use duplicate clusters to collapse redundant review and isolate derivative media.",
            "Prioritize decoder failures, signature mismatches, and GPS-enabled files first.",
        ])
        return "\n\n".join(lines)

    def _build_hidden_content_text(self, record: EvidenceRecord) -> str:
        lines = [
            record.hidden_content_overview,
            "",
            f"Primary issue: {record.score_primary_issue}",
            f"Tier summary: {record.hidden_context_summary}",
            f"Finding types: {', '.join(record.hidden_finding_types) if record.hidden_finding_types else 'None'}",
            f"URLs recovered: {len(record.urls_found)}",
            f"Readable strings kept for context: {len(record.extracted_strings)}",
            f"Code-like indicators: {len(record.hidden_code_indicators)}",
            f"Structural warnings: {len(record.hidden_suspicious_embeds)}",
            f"Container findings: {len(record.hidden_container_findings)}",
            f"Carved payloads: {len(record.hidden_carved_files)}",
            f"Carved summary: {record.hidden_carved_summary}",
            f"Stego / appended-payload note: {record.stego_suspicion}",
            f"OCR entities: apps {', '.join(record.ocr_app_names) if record.ocr_app_names else 'None'} • locations {', '.join(record.ocr_location_entities[:3]) if record.ocr_location_entities else 'None'}",
            "",
            "Interpretation:",
        ]
        if record.hidden_code_indicators:
            lines.append("Potential script-like, credential-like, or payload-bearing content was recovered from inside the container. Treat it as a heuristic lead and verify manually before drawing exploit conclusions.")
        elif record.hidden_suspicious_embeds:
            lines.append("No direct code payload was confirmed, but the container has structural hidden-content warnings such as encoded blobs or trailing data that justify a deeper review.")
        elif record.extracted_strings:
            lines.append("Readable strings exist inside the file, but they do not currently look like strong executable payloads. They are preserved as analyst context and may still help with provenance, origin tracing, or hidden-message review.")
        else:
            lines.append("No readable payload strings or code markers were recovered from the file bytes during the lightweight scan.")
        if record.hidden_carved_files:
            lines.extend(["", "Recovered payload files:"])
            lines.extend([f"- {item}" for item in record.hidden_carved_files[:4]])
        elif record.hidden_container_findings:
            lines.extend(["", "Container findings:"])
            lines.extend([f"- {item}" for item in record.hidden_container_findings[:6]])
        return "\n".join(lines)


    def _build_hidden_content_dump(self, record: EvidenceRecord) -> str:
        lines = ["[ EMBEDDED TEXT / CODE-LIKE MARKER SCAN ]", "=" * 96]
        if record.hidden_finding_types:
            lines.append(f"Finding types: {', '.join(record.hidden_finding_types)}")
            lines.append("")
        if record.urls_found:
            lines.append("URLs / external references:")
            lines.extend(f"- {url}" for url in record.urls_found)
            lines.append("")
        if record.hidden_code_indicators:
            lines.append("Code-like indicators:")
            lines.extend(f"- {item}" for item in record.hidden_code_indicators)
            lines.append("")
        if record.hidden_suspicious_embeds:
            lines.append("Structural hidden-content warnings:")
            lines.extend(f"- {item}" for item in record.hidden_suspicious_embeds)
            lines.append("")
        if record.hidden_payload_markers:
            lines.append("Payload-marker snippets:")
            lines.extend(f"- {item}" for item in record.hidden_payload_markers)
            lines.append("")
        if record.hidden_container_findings:
            lines.append("Container findings:")
            lines.extend(f"- {item}" for item in record.hidden_container_findings)
            lines.append("")
        if record.hidden_carved_files:
            lines.append("Recovered payload files:")
            lines.extend(f"- {item}" for item in record.hidden_carved_files)
            lines.append("")
        if record.visible_urls or record.visible_text_lines:
            lines.append("Visible OCR clues:")
            lines.extend(f"- {item}" for item in (record.visible_urls[:4] + record.visible_text_lines[:6]))
            lines.append("")
        if record.extracted_strings:
            lines.append("Readable embedded strings (context only):")
            lines.extend(f"- {item}" for item in record.extracted_strings)
        else:
            lines.append("No readable strings recovered.")
        if len(lines) <= 2:
            lines.append("No embedded text markers recovered.")
        return "\n".join(lines)

    def _build_review_audit_text(self, record: EvidenceRecord) -> str:
        logs = self.case_manager.db.fetch_logs(self.case_manager.active_case_id)
        lines = ["[ REVIEW-SCOPED AUDIT ]", "=" * 96]
        if record.custody_event_summary:
            lines.append("Recent evidence-scoped events:")
            lines.extend(f"- {item}" for item in record.custody_event_summary)
            lines.append("")
        selected = []
        for row in logs:
            if row["evidence_id"] in {None, record.evidence_id}:
                label = f"[{row['action']}]"
                selected.append(f"{row['action_time']} {label:<18} {row['evidence_id'] or 'CASE':<10} {row['details']} | hash={str(row['event_hash'] or 'legacy')[:10]}")
        lines.extend(selected[:40] if selected else ["No case events found for the selected evidence item."])
        return "\n".join(lines)

    def _build_verdict_panel_text(self, record: EvidenceRecord) -> str:
        top = ", ".join(record.anomaly_contributors[:3]) if record.anomaly_contributors else "No major anomaly contributor"
        recommendation = record.metadata_recommendations[0] if record.metadata_recommendations else record.score_next_step
        lines = [
            f"{record.evidence_id} • {record.source_type}",
            f"Primary issue: {record.score_primary_issue}",
            f"Why it matters: {record.score_reason}",
            f"Recommended next step: {recommendation}",
            f"Time anchor: {record.timestamp_source} ({record.timestamp_confidence}%)",
            f"Value {record.evidentiary_value}% • Courtroom {record.courtroom_strength}%",
            f"Top signal: {top}",
        ]
        if record.validation_hits or record.validation_misses:
            lines.append(f"Validation: {len(record.validation_hits)} hit(s), {len(record.validation_misses)} miss(es)")
        lines.append(record.courtroom_notes or record.analyst_verdict or "No focused verdict is available.")
        return "\n".join(lines)




    def _build_geo_map_context_text(self, record):
        route_state = "Detected" if record.route_overlay_detected else "Not detected"
        lines = [
            "[ MAP INTELLIGENCE / OSINT AI ]",
            f"- App detected: {record.map_app_detected}",
            f"- Map type: {record.map_type}",
            f"- Route overlay: {route_state} ({record.route_confidence}%)",
            f"- Candidate city: {record.candidate_city}",
            f"- Candidate area: {record.candidate_area}",
            f"- Possible place: {record.possible_place}",
            f"- Map confidence: {record.map_confidence}%",
            f"- OCR language hint: {record.map_ocr_language_hint}",
            f"- Evidence basis: {', '.join(record.map_evidence_basis) if record.map_evidence_basis else 'Not available'}",
            f"- OSINT AI scene read: {record.osint_scene_label} ({record.osint_scene_confidence}%)",
            f"- OSINT Content v2: {record.osint_content_label} ({record.osint_content_confidence}%)",
            f"- Source context: {record.osint_source_context}",
        ]
        if record.osint_content_tags:
            lines.append("- Content tags: " + ", ".join(record.osint_content_tags[:6]))
        if record.osint_location_hypotheses:
            lines.append("- Location hypotheses: " + " | ".join(record.osint_location_hypotheses[:3]))
        if record.osint_next_actions:
            lines.append("- OSINT next actions: " + " | ".join(record.osint_next_actions[:3]))
        if record.landmarks_detected:
            lines.append("- Landmarks detected: " + ", ".join(record.landmarks_detected[:5]))
        if record.place_candidates:
            lines.append("- Place candidates: " + ", ".join(record.place_candidates[:5]))
        if record.place_candidate_rankings:
            lines.append("- Candidate ranking: " + " | ".join(record.place_candidate_rankings[:4]))
        if record.map_intelligence_reasons:
            lines.append("- Map intelligence reasons: " + "; ".join(record.map_intelligence_reasons[:4]))
        if record.osint_scene_reasons:
            lines.append("- Scene reasoning: " + "; ".join(record.osint_scene_reasons[:3]))
        if record.derived_geo_display != "Unavailable":
            lines.append(f"- Derived geo display: {record.derived_geo_display} ({record.derived_geo_confidence}%)")
        elif record.possible_geo_clues:
            lines.append("- Supporting geo clues: " + ", ".join(record.possible_geo_clues[:4]))
        if record.ocr_map_labels:
            lines.append("- OCR map labels: " + ", ".join(record.ocr_map_labels[:4]))
        lines.append("")
        lines.append(record.map_intelligence_summary or record.osint_scene_summary)
        return "\n".join(lines).strip()
