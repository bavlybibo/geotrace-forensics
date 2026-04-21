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
    file_size: int
    imported_at: str
    exif: Dict[str, str] = field(default_factory=dict)
    timestamp: str = "Unknown"
    device_model: str = "Unknown"
    software: str = "N/A"
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_display: str = "Unavailable"
    anomaly_reasons: List[str] = field(default_factory=list)
    suspicion_score: int = 0
    risk_level: str = "Low"
    integrity_status: str = "Verified"
    note: str = ""
    width: int = 0
    height: int = 0

    @property
    def has_gps(self) -> bool:
        return self.gps_latitude is not None and self.gps_longitude is not None


@dataclass
class CaseStats:
    total_images: int = 0
    gps_enabled: int = 0
    anomaly_count: int = 0
    device_count: int = 0
    timeline_span: str = "N/A"
    integrity_summary: str = "0/0 Verified"
