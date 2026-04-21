from __future__ import annotations

from pathlib import Path
from typing import Iterable

import folium

from .models import EvidenceRecord


class MapService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def create_map(self, records: Iterable[EvidenceRecord]) -> Path | None:
        gps_records = [record for record in records if record.has_gps]
        if not gps_records:
            return None

        center_lat = sum(record.gps_latitude for record in gps_records if record.gps_latitude is not None) / len(gps_records)
        center_lon = sum(record.gps_longitude for record in gps_records if record.gps_longitude is not None) / len(gps_records)
        evidence_map = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="CartoDB dark_matter")

        points = []
        for record in gps_records:
            points.append([record.gps_latitude, record.gps_longitude])
            popup_html = f"""
            <b>{record.evidence_id}</b><br>
            File: {record.file_name}<br>
            Time: {record.timestamp}<br>
            Device: {record.device_model}<br>
            Risk: {record.risk_level} ({record.suspicion_score})
            """
            folium.Marker(
                [record.gps_latitude, record.gps_longitude],
                popup=popup_html,
                tooltip=record.file_name,
                icon=folium.Icon(color="lightblue", icon="camera"),
            ).add_to(evidence_map)

        if len(points) > 1:
            folium.PolyLine(points, weight=2.5, color="#00d5ff", opacity=0.75).add_to(evidence_map)

        output = self.export_dir / "geolocation_map.html"
        evidence_map.save(str(output))
        return output
