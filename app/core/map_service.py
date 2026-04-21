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
        evidence_map = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
        folium.TileLayer("CartoDB dark_matter", name="Dark").add_to(evidence_map)
        folium.TileLayer("CartoDB positron", name="Light").add_to(evidence_map)

        points = []
        risk_colors = {"High": "red", "Medium": "orange", "Low": "blue"}
        for record in gps_records:
            points.append([record.gps_latitude, record.gps_longitude])
            popup_html = f"""
            <div style='font-family:Segoe UI,Arial,sans-serif;min-width:240px;'>
                <h4 style='margin:0 0 8px 0;'>{record.evidence_id}</h4>
                <b>File:</b> {record.file_name}<br>
                <b>Time:</b> {record.timestamp} ({record.timestamp_source})<br>
                <b>Device:</b> {record.device_model}<br>
                <b>Source:</b> {record.source_type}<br>
                <b>Risk:</b> {record.risk_level} ({record.suspicion_score})<br>
                <b>GPS:</b> {record.gps_display}
            </div>
            """
            folium.Marker(
                [record.gps_latitude, record.gps_longitude],
                popup=popup_html,
                tooltip=f"{record.evidence_id} • {record.file_name}",
                icon=folium.Icon(color=risk_colors.get(record.risk_level, "blue"), icon="camera", prefix="fa"),
            ).add_to(evidence_map)

        if len(points) > 1:
            folium.PolyLine(points, weight=3, color="#00d5ff", opacity=0.75, tooltip="Temporal movement path").add_to(evidence_map)

        folium.LayerControl().add_to(evidence_map)
        output = self.export_dir / "geolocation_map.html"
        evidence_map.save(str(output))
        return output
