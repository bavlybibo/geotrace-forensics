from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class EvidenceRecord:
    evidence_id: str
    file_path: Path
    file_name: str
    sha256: str
    md5: str
    perceptual_hash: str
    file_size: int
    imported_at: str
    exif: Dict[str, str] = field(default_factory=dict)
    timestamp: str = "Unknown"
    timestamp_source: str = "Unavailable"
    created_time: str = "Unknown"
    modified_time: str = "Unknown"
    device_model: str = "Unknown"
    camera_make: str = "Unknown"
    software: str = "N/A"
    source_type: str = "Unknown"
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
    anomaly_reasons: List[str] = field(default_factory=list)
    osint_leads: List[str] = field(default_factory=list)
    suspicion_score: int = 0
    confidence_score: int = 0
    risk_level: str = "Low"
    integrity_status: str = "Verified"
    note: str = ""
    width: int = 0
    height: int = 0
    megapixels: float = 0.0
    aspect_ratio: str = "Unknown"
    brightness_mean: float = 0.0
    duplicate_group: str = ""
    analyst_verdict: str = ""

    @property
    def has_gps(self) -> bool:
        return self.gps_latitude is not None and self.gps_longitude is not None

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "Unknown"


@dataclass
class CaseStats:
    total_images: int = 0
    gps_enabled: int = 0
    anomaly_count: int = 0
    device_count: int = 0
    timeline_span: str = "N/A"
    integrity_summary: str = "0/0 Verified"
    screenshots_count: int = 0
    duplicates_count: int = 0
    avg_score: int = 0
