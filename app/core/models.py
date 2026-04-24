from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


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
    validation_hits: List[str] = field(default_factory=list)
    validation_misses: List[str] = field(default_factory=list)
    extracted_strings: List[str] = field(default_factory=list)
    visible_text_lines: List[str] = field(default_factory=list)
    ocr_raw_text: str = ""
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
