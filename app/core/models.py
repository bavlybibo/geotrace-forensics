from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GeoProfile:
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    gps_display: str = "Unavailable"
    gps_source: str = "Unavailable"
    gps_confidence: int = 0
    derived_geo_display: str = "Unavailable"
    derived_geo_source: str = "Unavailable"
    derived_geo_confidence: int = 0
    geo_status: str = "No native GPS recovered."
    map_confidence: int = 0
    possible_place: str = "Unavailable"
    evidence_strength: str = "weak_signal"


@dataclass
class OCRProfile:
    raw_text: str = ""
    note: str = "OCR not attempted."
    confidence: int = 0
    analyst_relevance: str = "OCR not attempted."
    visible_lines: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    times: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    usernames: List[str] = field(default_factory=list)
    map_labels: List[str] = field(default_factory=list)


@dataclass
class AIProfile:
    provider: str = "Not evaluated"
    risk_label: str = "Not evaluated"
    confidence: int = 0
    score_delta: int = 0
    summary: str = "AI batch assessment has not run for this evidence."
    flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    action_plan: List[str] = field(default_factory=list)
    evidence_strength: str = "weak_signal"
    courtroom_readiness: str = "Ready for courtroom: Pending AI review."
    next_best_action: str = "No AI next-best-action generated yet."
    privacy_audit: str = "AI privacy auditor has not run yet."


@dataclass
class EvidenceRecord:
    case_id: str
    case_name: str
    evidence_id: str
    file_path: Path
    file_name: str
    sha256: str
    md5: str
    perceptual_hash: str
    file_size: int
    imported_at: str
    original_file_path: Path = Path(".")
    working_copy_path: Path = Path(".")
    source_sha256: str = ""
    source_md5: str = ""
    working_sha256: str = ""
    working_md5: str = ""
    copy_verified: bool = False
    acquisition_note: str = "Source/working-copy hash comparison has not been recorded yet."
    exif: Dict[str, str] = field(default_factory=dict)
    raw_exif: Dict[str, str] = field(default_factory=dict)
    container_metadata: Dict[str, str] = field(default_factory=dict)
    exif_warning: str = ""
    timestamp: str = "Unknown"
    timestamp_source: str = "Unavailable"
    timestamp_confidence: int = 0
    timestamp_verdict: str = "No trusted time anchor recovered yet."
    created_time: str = "Unavailable"
    created_time_note: str = "Birth/creation time is not available yet."
    modified_time: str = "Unknown"
    device_model: str = "Unknown"
    camera_make: str = "Unknown"
    software: str = "N/A"
    source_type: str = "Unknown"
    source_subtype: str = "Unknown"
    source_profile_confidence: int = 0
    source_profile_reasons: List[str] = field(default_factory=list)
    environment_profile: str = "Unknown"
    app_detected: str = "Unknown"
    scene_group: str = ""
    similarity_score: int = 0
    similarity_note: str = "No peer-similarity reading generated yet."
    format_name: str = "Unknown"
    color_mode: str = "Unknown"
    has_alpha: bool = False
    dpi: str = "N/A"
    orientation: str = "Unknown"
    lens_model: str = "N/A"
    iso: str = "N/A"
    exposure_time: str = "N/A"
    f_number: str = "N/A"
    focal_length: str = "N/A"
    artist: str = "N/A"
    copyright_notice: str = "N/A"
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    gps_display: str = "Unavailable"
    gps_source: str = "Unavailable"
    gps_confidence: int = 0
    gps_verification: str = "No native GPS recovered."
    derived_latitude: Optional[float] = None
    derived_longitude: Optional[float] = None
    derived_geo_display: str = "Unavailable"
    derived_geo_source: str = "Unavailable"
    derived_geo_confidence: int = 0
    derived_geo_note: str = "No screenshot-derived geolocation clue recovered."
    geo_status: str = "No native GPS recovered."
    gps_ladder: List[str] = field(default_factory=list)
    gps_primary_issue: str = "No GPS issue summary generated."
    metadata_issues: List[str] = field(default_factory=list)
    metadata_strengths: List[str] = field(default_factory=list)
    metadata_recommendations: List[str] = field(default_factory=list)
    metadata_issue_summary: str = "No metadata issue summary generated."
    anomaly_reasons: List[str] = field(default_factory=list)
    anomaly_contributors: List[str] = field(default_factory=list)
    manipulation_flags: List[str] = field(default_factory=list)
    osint_leads: List[str] = field(default_factory=list)
    suspicion_score: int = 0
    confidence_score: int = 0
    risk_level: str = "Low"
    integrity_status: str = "Pending Review"
    integrity_note: str = "Structural verification has not been finalized yet."
    note: str = ""
    tags: str = ""
    bookmarked: bool = False
    width: int = 0
    height: int = 0
    megapixels: float = 0.0
    aspect_ratio: str = "Unknown"
    brightness_mean: float = 0.0
    duplicate_group: str = ""
    duplicate_relation: str = ""
    duplicate_method: str = ""
    duplicate_peers: List[str] = field(default_factory=list)
    duplicate_distance: int = 0
    analyst_verdict: str = ""
    courtroom_notes: str = ""
    parser_status: str = "Valid"
    preview_status: str = "Ready"
    structure_status: str = "Valid"
    format_signature: str = "Unknown"
    format_trust: str = "Unverified"
    signature_status: str = "Unknown"
    parse_error: str = ""
    frame_count: int = 1
    is_animated: bool = False
    animation_duration_ms: int = 0
    authenticity_score: int = 0
    metadata_score: int = 0
    technical_score: int = 0
    score_breakdown: List[str] = field(default_factory=list)
    score_primary_issue: str = "No primary score issue identified."
    score_reason: str = "No score reason generated."
    score_next_step: str = "No next step generated."
    score_summary: str = "No explainability summary generated."
    ai_provider: str = "Not evaluated"
    ai_score_delta: int = 0
    ai_confidence: int = 0
    ai_risk_label: str = "Not evaluated"
    ai_summary: str = "AI batch assessment has not run for this evidence."
    ai_flags: List[str] = field(default_factory=list)
    ai_reasons: List[str] = field(default_factory=list)
    ai_breakdown: List[str] = field(default_factory=list)
    ai_action_plan: List[str] = field(default_factory=list)
    ai_corroboration_matrix: List[str] = field(default_factory=list)
    ai_case_links: List[str] = field(default_factory=list)
    ai_evidence_graph: List[str] = field(default_factory=list)
    ai_contradiction_explainer: List[str] = field(default_factory=list)
    ai_courtroom_readiness: str = "Ready for courtroom: Pending AI review."
    ai_next_best_action: str = "No AI next-best-action generated yet."
    ai_privacy_audit: str = "AI privacy auditor has not run yet."
    ai_executive_note: str = "No AI priority note generated yet."
    ai_priority_rank: int = 0
    evidence_strength_label: str = "weak_signal"
    evidence_strength_score: int = 0
    evidence_strength_reasons: List[str] = field(default_factory=list)
    evidence_strength_limitations: List[str] = field(default_factory=list)
    osint_scene_label: str = "Unclassified"
    osint_scene_confidence: int = 0
    osint_scene_summary: str = "OSINT AI content read has not been generated yet."
    osint_scene_reasons: List[str] = field(default_factory=list)
    osint_content_label: str = "Unclassified image content"
    osint_content_confidence: int = 0
    osint_content_summary: str = "OSINT Content v2 has not been generated yet."
    osint_content_tags: List[str] = field(default_factory=list)
    osint_visual_cues: List[str] = field(default_factory=list)
    osint_text_cues: List[str] = field(default_factory=list)
    osint_location_hypotheses: List[str] = field(default_factory=list)
    osint_source_context: str = "Unknown"
    osint_content_limitations: List[str] = field(default_factory=list)
    osint_next_actions: List[str] = field(default_factory=list)
    image_detail_label: str = "Image detail profile unavailable"
    image_detail_confidence: int = 0
    image_detail_summary: str = "Image-detail analysis has not run yet."
    image_detail_cues: List[str] = field(default_factory=list)
    image_layout_hints: List[str] = field(default_factory=list)
    image_object_hints: List[str] = field(default_factory=list)
    image_quality_flags: List[str] = field(default_factory=list)
    image_detail_metrics: Dict[str, object] = field(default_factory=dict)
    image_detail_limitations: List[str] = field(default_factory=list)
    image_detail_next_actions: List[str] = field(default_factory=list)
    image_attention_regions: List[Dict[str, object]] = field(default_factory=list)
    image_scene_descriptors: List[str] = field(default_factory=list)
    image_analysis_methodology: List[str] = field(default_factory=list)
    image_performance_notes: List[str] = field(default_factory=list)
    osint_entities: List[Dict[str, object]] = field(default_factory=list)
    osint_hypothesis_cards: List[Dict[str, object]] = field(default_factory=list)
    osint_corroboration_matrix: List[Dict[str, object]] = field(default_factory=list)
    osint_analyst_decisions: List[Dict[str, object]] = field(default_factory=list)
    osint_privacy_review: Dict[str, object] = field(default_factory=dict)
    osint_cache_status: str = "OSINT cache not written yet."
    ocr_region_signals: List[Dict[str, object]] = field(default_factory=list)
    detected_map_context: str = "No clear map/location context was recovered from the current evidence item."
    possible_place: str = "Unavailable"
    map_confidence: int = 0
    map_app_detected: str = "Unknown"
    map_type: str = "Unknown"
    route_overlay_detected: bool = False
    route_confidence: int = 0
    candidate_city: str = "Unavailable"
    candidate_area: str = "Unavailable"
    landmarks_detected: List[str] = field(default_factory=list)
    place_candidates: List[str] = field(default_factory=list)
    map_intelligence_confidence: int = 0
    map_ocr_language_hint: str = "Unknown"
    map_intelligence_summary: str = "No map intelligence generated yet."
    map_intelligence_reasons: List[str] = field(default_factory=list)
    map_evidence_basis: List[str] = field(default_factory=list)
    map_evidence_strength: str = "weak_signal"
    map_limitations: List[str] = field(default_factory=list)
    map_recommended_actions: List[str] = field(default_factory=list)
    map_evidence_ladder: List[str] = field(default_factory=list)
    map_visual_profile: Dict[str, object] = field(default_factory=dict)
    map_anchor_status: str = "No stable map/location anchor recovered."
    map_answer_readiness_score: int = 0
    map_answer_readiness_label: str = "Not answer-ready"
    map_extraction_plan: List[str] = field(default_factory=list)
    map_route_start_label: str = ""
    map_route_end_label: str = ""
    map_label_clusters: List[Dict[str, object]] = field(default_factory=list)
    map_confidence_radius_m: int = 0
    map_offline_geocoder_hits: List[Dict[str, object]] = field(default_factory=list)
    map_source_comparison: List[str] = field(default_factory=list)
    map_interactive_payload: Dict[str, object] = field(default_factory=dict)
    place_candidate_rankings: List[str] = field(default_factory=list)
    filename_location_hints: List[str] = field(default_factory=list)
    ctf_clues: List[Dict[str, object]] = field(default_factory=list)
    geo_candidates: List[Dict[str, object]] = field(default_factory=list)
    ctf_search_queries: List[str] = field(default_factory=list)
    location_solvability_score: int = 0
    location_solvability_label: str = "No useful geo clue"
    location_estimate_label: str = "Unavailable"
    location_estimate_confidence: int = 0
    location_estimate_scope: str = "no_signal"
    location_estimate_source_tier: str = "no_signal"
    location_estimate_summary: str = "No stable location estimate was recovered yet."
    location_estimate_supporting_signals: List[str] = field(default_factory=list)
    location_estimate_limitations: List[str] = field(default_factory=list)
    location_estimate_next_actions: List[str] = field(default_factory=list)
    location_estimate_candidates: List[str] = field(default_factory=list)
    ctf_country_region_profile: str = "Unknown"
    ctf_landmark_matches: List[Dict[str, object]] = field(default_factory=list)
    ctf_writeup: str = "CTF geolocation writeup has not been generated yet."
    ctf_online_mode_status: str = "Offline-only. External/reverse-image searches require explicit analyst action and privacy review."
    ctf_image_existence_profile: Dict[str, object] = field(default_factory=dict)
    ctf_online_privacy_review: Dict[str, object] = field(default_factory=dict)
    ctf_visual_clue_profile: Dict[str, object] = field(default_factory=dict)
    pixel_hidden_score: int = 0
    pixel_hidden_verdict: str = "Not evaluated"
    pixel_hidden_summary: str = "Pixel-level hidden-content scan has not run yet."
    pixel_hidden_indicators: List[str] = field(default_factory=list)
    pixel_lsb_strings: List[str] = field(default_factory=list)
    pixel_alpha_findings: List[str] = field(default_factory=list)
    pixel_channel_notes: List[str] = field(default_factory=list)
    pixel_hidden_metrics: Dict[str, object] = field(default_factory=dict)
    pixel_hidden_limitations: List[str] = field(default_factory=list)
    pixel_hidden_next_actions: List[str] = field(default_factory=list)
    manual_crop_assets: List[str] = field(default_factory=list)
    ocr_diagnostics: Dict[str, object] = field(default_factory=dict)
    validation_hits: List[str] = field(default_factory=list)
    validation_misses: List[str] = field(default_factory=list)
    extracted_strings: List[str] = field(default_factory=list)
    visible_text_lines: List[str] = field(default_factory=list)
    ocr_raw_text: str = ""
    ocr_note: str = "OCR not attempted."
    ocr_confidence: int = 0
    ocr_analyst_relevance: str = "OCR not attempted."
    ocr_app_names: List[str] = field(default_factory=list)
    ocr_username_entities: List[str] = field(default_factory=list)
    ocr_map_labels: List[str] = field(default_factory=list)
    visible_urls: List[str] = field(default_factory=list)
    ocr_url_entities: List[str] = field(default_factory=list)
    visible_time_strings: List[str] = field(default_factory=list)
    ocr_time_entities: List[str] = field(default_factory=list)
    visible_location_strings: List[str] = field(default_factory=list)
    ocr_location_entities: List[str] = field(default_factory=list)
    possible_geo_clues: List[str] = field(default_factory=list)
    visible_text_excerpt: str = ""
    hidden_code_indicators: List[str] = field(default_factory=list)
    hidden_finding_types: List[str] = field(default_factory=list)
    hidden_code_summary: str = "No embedded code-like content detected."
    hidden_content_overview: str = "No embedded text payloads or code-like markers detected."
    hidden_context_summary: str = "No visible or embedded text context was retained."
    hidden_suspicious_embeds: List[str] = field(default_factory=list)
    hidden_payload_markers: List[str] = field(default_factory=list)
    hidden_container_findings: List[str] = field(default_factory=list)
    hidden_carved_files: List[str] = field(default_factory=list)
    hidden_carved_summary: str = "No carved payload segments were recovered."
    stego_suspicion: str = "No strong steganography or appended-payload indicator was detected."
    urls_found: List[str] = field(default_factory=list)
    time_candidates: List[str] = field(default_factory=list)
    time_conflicts: List[str] = field(default_factory=list)
    custody_event_summary: List[str] = field(default_factory=list)

    @property
    def geo_profile(self) -> GeoProfile:
        return GeoProfile(gps_latitude=self.gps_latitude, gps_longitude=self.gps_longitude, gps_altitude=self.gps_altitude, gps_display=self.gps_display, gps_source=self.gps_source, gps_confidence=self.gps_confidence, derived_geo_display=self.derived_geo_display, derived_geo_source=self.derived_geo_source, derived_geo_confidence=self.derived_geo_confidence, geo_status=self.geo_status, map_confidence=max(self.map_confidence, self.map_intelligence_confidence), possible_place=self.possible_place, evidence_strength=self.map_evidence_strength)

    @property
    def ocr_profile(self) -> OCRProfile:
        return OCRProfile(raw_text=self.ocr_raw_text, note=self.ocr_note, confidence=self.ocr_confidence, analyst_relevance=self.ocr_analyst_relevance, visible_lines=list(self.visible_text_lines), urls=list(self.ocr_url_entities or self.visible_urls), times=list(self.ocr_time_entities or self.visible_time_strings), locations=list(self.ocr_location_entities or self.visible_location_strings), usernames=list(self.ocr_username_entities), map_labels=list(self.ocr_map_labels))

    @property
    def ai_profile(self) -> AIProfile:
        return AIProfile(provider=self.ai_provider, risk_label=self.ai_risk_label, confidence=self.ai_confidence, score_delta=self.ai_score_delta, summary=self.ai_summary, flags=list(self.ai_flags), reasons=list(self.ai_reasons), action_plan=list(self.ai_action_plan), evidence_strength=self.evidence_strength_label, courtroom_readiness=self.ai_courtroom_readiness, next_best_action=self.ai_next_best_action, privacy_audit=self.ai_privacy_audit)

    @property
    def has_gps(self) -> bool:
        return self.gps_latitude is not None and self.gps_longitude is not None

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "Unknown"

    @property
    def evidentiary_value(self) -> int:
        value = 0
        if self.timestamp_confidence >= 90:
            value += 28
        elif self.timestamp_confidence >= 70:
            value += 20
        elif self.timestamp_confidence > 0:
            value += 12

        if self.gps_confidence >= 80:
            value += 26
        elif self.has_gps:
            value += 18
        elif self.derived_geo_confidence >= 60:
            value += 14
        elif self.derived_geo_confidence > 0:
            value += 8

        if self.integrity_status == "Verified":
            value += 16
        elif self.integrity_status == "Partial":
            value += 10

        if self.device_model not in {"Unknown", "N/A", ""}:
            value += 6
        if self.visible_text_excerpt:
            value += 6
        if self.duplicate_group:
            value += 5
        if self.hidden_code_indicators or self.hidden_suspicious_embeds:
            value += 7
        if self.signature_status == "Mismatch" or self.parser_status != "Valid":
            value = max(8, value - 10)
        return max(0, min(100, value))

    @property
    def evidentiary_label(self) -> str:
        value = self.evidentiary_value
        if value >= 72:
            return "High"
        if value >= 45:
            return "Medium"
        return "Low"

    @property
    def courtroom_strength(self) -> int:
        strength = 0
        if self.timestamp_confidence >= 90:
            strength += 28
        elif self.timestamp_confidence >= 70:
            strength += 18
        elif self.timestamp_confidence > 0:
            strength += 8

        if self.gps_confidence >= 80:
            strength += 22
        elif self.has_gps:
            strength += 14
        elif self.derived_geo_confidence >= 60:
            strength += 10
        elif self.derived_geo_confidence > 0:
            strength += 5

        if self.integrity_status == "Verified":
            strength += 20
        elif self.integrity_status == "Partial":
            strength += 12

        if self.signature_status in {"Matched", "Compatible"}:
            strength += 8
        if self.parser_status == "Valid":
            strength += 6
        if self.device_model not in {"Unknown", "N/A", ""}:
            strength += 5
        if self.visible_text_excerpt:
            strength += 4
        if self.time_conflicts:
            strength -= 10
        if self.hidden_code_indicators:
            strength -= 8
        if self.parser_status != "Valid" or self.signature_status == "Mismatch":
            strength -= 14
        return max(0, min(100, strength))

    @property
    def courtroom_label(self) -> str:
        value = self.courtroom_strength
        if value >= 68:
            return "High"
        if value >= 40:
            return "Medium"
        return "Low"


@dataclass
class CaseStats:
    total_images: int = 0
    gps_enabled: int = 0
    anomaly_count: int = 0
    device_count: int = 0
    timeline_span: str = "N/A"
    integrity_summary: str = "0/0 Checked"
    screenshots_count: int = 0
    duplicates_count: int = 0
    avg_score: int = 0
    parser_issue_count: int = 0
    hidden_content_count: int = 0
    bookmarked_count: int = 0
    validation_summary: str = "Validation pending"


@dataclass
class CaseInfo:
    case_id: str
    case_name: str
    created_at: str
    updated_at: str
    item_count: int = 0
