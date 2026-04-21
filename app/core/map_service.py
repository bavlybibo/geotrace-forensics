from __future__ import annotations

from pathlib import Path
from typing import Iterable

import folium

from .anomalies import parse_timestamp
from .models import EvidenceRecord


class MapService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def create_map(self, records: Iterable[EvidenceRecord]) -> Path | None:
        plot_records = [record for record in records if record.has_gps or (record.derived_latitude is not None and record.derived_longitude is not None)]
        if not plot_records:
            return None

        def _lat(record: EvidenceRecord) -> float:
            return record.gps_latitude if record.gps_latitude is not None else float(record.derived_latitude)

        def _lon(record: EvidenceRecord) -> float:
            return record.gps_longitude if record.gps_longitude is not None else float(record.derived_longitude)

        ordered_records = sorted(plot_records, key=lambda item: (parse_timestamp(item.timestamp) is None, parse_timestamp(item.timestamp) or item.timestamp, item.evidence_id))
        center_lat = sum(_lat(record) for record in ordered_records) / len(ordered_records)
        center_lon = sum(_lon(record) for record in ordered_records) / len(ordered_records)
        evidence_map = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
        folium.TileLayer("CartoDB dark_matter", name="Dark").add_to(evidence_map)
        folium.TileLayer("CartoDB positron", name="Light").add_to(evidence_map)

        points = []
        risk_colors = {"High": "red", "Medium": "orange", "Low": "blue"}
        for idx, record in enumerate(ordered_records, start=1):
            latitude = _lat(record)
            longitude = _lon(record)
            points.append([latitude, longitude])
            popup_html = f"""
            <div style='font-family:Segoe UI,Arial,sans-serif;min-width:270px;'>
                <h4 style='margin:0 0 8px 0;'>#{idx:02d} • {record.evidence_id}</h4>
                <b>File:</b> {record.file_name}<br>
                <b>Time:</b> {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)<br>
                <b>Risk / Score:</b> {record.risk_level} ({record.suspicion_score})<br>
                <b>Analytic confidence:</b> {record.confidence_score}%<br>
                <b>Evidentiary value:</b> {record.evidentiary_value}% ({record.evidentiary_label})<br>
                <b>Device:</b> {record.device_model}<br>
                <b>Source:</b> {record.source_type}<br>
                <b>Native GPS:</b> {record.gps_display}<br>
                <b>Derived Geo:</b> {record.derived_geo_display}<br>
                <b>SHA-256:</b> {record.sha256[:16]}…{record.sha256[-12:]}
            </div>
            """
            folium.Marker(
                [latitude, longitude],
                popup=popup_html,
                tooltip=f"#{idx:02d} • {record.evidence_id} • {record.file_name}",
                icon=folium.Icon(color=risk_colors.get(record.risk_level, "blue"), icon="camera" if record.has_gps else "map-pin", prefix="fa"),
            ).add_to(evidence_map)
            confidence_radius = 55 + (record.gps_confidence or record.derived_geo_confidence) * 2.8
            folium.Circle(
                location=[latitude, longitude],
                radius=confidence_radius,
                color="#38d8ff" if record.has_gps else "#ffd166",
                fill=True,
                fill_opacity=0.12,
                weight=2,
                tooltip=f"Confidence halo • {record.gps_confidence if record.has_gps else record.derived_geo_confidence}%",
            ).add_to(evidence_map)

        if len(points) > 1:
            folium.PolyLine(points, weight=3, color="#00d5ff", opacity=0.75, tooltip="Chronology path").add_to(evidence_map)
            evidence_map.fit_bounds(points, padding=(25, 25))
        else:
            evidence_map.location = points[0]
            evidence_map.zoom_start = 11

        legend = """
        <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999; background: rgba(7,17,27,0.92); color: #eaf7ff; border: 1px solid #1b4c71; border-radius: 12px; padding: 12px 14px; min-width: 230px; font-family: Segoe UI, Arial, sans-serif; font-size: 13px; box-shadow: 0 12px 30px rgba(0,0,0,0.28);">
            <div style="font-weight:700; margin-bottom:6px;">Map intelligence</div>
            <div>Markers are ordered chronologically when time anchors exist.</div>
            <div style="margin-top:6px;">Blue halo = native GPS confidence.</div>
            <div>Amber halo = derived/screenshot geo confidence.</div>
            <div style="margin-top:6px;">Open popups for hashes, value, and anchor strength.</div>
        </div>
        """
        evidence_map.get_root().html.add_child(folium.Element(legend))
        folium.LayerControl().add_to(evidence_map)
        output = self.export_dir / "geolocation_map.html"
        evidence_map.save(str(output))
        return output
