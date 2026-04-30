from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

import folium

from .anomalies import parse_timestamp
from .models import EvidenceRecord
from .map.evidence import anchor_kind_from_source, claim_policy_for_anchor


PLACE_COORDINATES: dict[str, tuple[float, float, str]] = {
    # Approximate city/area/landmark centroids used only when the evidence has a
    # visible/OCR/place-dictionary lead but no exact GPS. Popups label these as
    # approximate so they never outrank native GPS or visible coordinates.
    "Cairo": (30.0444, 31.2357, "city centroid"),
    "Giza": (30.0131, 31.2089, "city centroid"),
    "Alexandria": (31.2001, 29.9187, "city centroid"),
    "Luxor": (25.6872, 32.6396, "city centroid"),
    "Aswan": (24.0889, 32.8998, "city centroid"),
    "Zamalek": (30.0606, 31.2197, "area centroid"),
    "Garden City": (30.0365, 31.2311, "area centroid"),
    "Heliopolis": (30.0914, 31.3227, "area centroid"),
    "Nasr City": (30.0561, 31.3301, "area centroid"),
    "New Cairo": (30.0074, 31.4913, "area centroid"),
    "Dokki": (30.0383, 31.2124, "area centroid"),
    "Mohandessin": (30.0556, 31.2008, "area centroid"),
    "Maadi": (29.9602, 31.2569, "area centroid"),
    "Tahrir": (30.0445, 31.2357, "landmark/area centroid"),
    "Nile Corniche": (30.0500, 31.2240, "linear feature approximation"),
    "Haram": (29.9870, 31.1370, "area centroid"),
    "6th of October": (29.9285, 30.9188, "city centroid"),
    "Cairo Tower": (30.0459, 31.2243, "landmark coordinate"),
    "Egyptian Museum": (30.0478, 31.2336, "landmark coordinate"),
    "Cairo Stadium": (30.0686, 31.3123, "landmark coordinate"),
    "Nile River": (30.0440, 31.2240, "feature approximation"),
    "Tahrir Square": (30.0444, 31.2357, "landmark coordinate"),
    "Giza Pyramids": (29.9792, 31.1342, "landmark coordinate"),
    "Khan el-Khalili": (30.0477, 31.2625, "landmark coordinate"),
    "Cairo International Airport": (30.1120, 31.4000, "landmark coordinate"),
    "Fairmont Nile City": (30.0716, 31.2274, "landmark coordinate"),
}


class MapService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _geo_point_for_record(self, record: EvidenceRecord) -> tuple[float, float, str, int, str] | None:
        if record.has_gps and record.gps_latitude is not None and record.gps_longitude is not None:
            return float(record.gps_latitude), float(record.gps_longitude), f"Native GPS ({record.gps_source})", int(record.gps_confidence or 0), "native_gps"
        if record.derived_latitude is not None and record.derived_longitude is not None:
            return float(record.derived_latitude), float(record.derived_longitude), f"Derived/visible coordinate ({record.derived_geo_source})", int(record.derived_geo_confidence or 0), "derived_coordinate"

        # Approximate place fallback for map screenshots after OCR/dictionary extraction.
        # This intentionally never triggers for visual-only strings like "light tiled map canvas".
        candidates: list[str] = []
        candidates.extend([str(x) for x in getattr(record, "landmarks_detected", []) or []])
        for value in [getattr(record, "candidate_area", ""), getattr(record, "candidate_city", "")]:
            if str(value or "") not in {"", "Unavailable", "Unknown", "None"}:
                candidates.append(str(value))
        for place in candidates:
            if place in PLACE_COORDINATES:
                lat, lon, kind = PLACE_COORDINATES[place]
                confidence = max(35, min(72, int(getattr(record, "map_answer_readiness_score", 0) or getattr(record, "map_intelligence_confidence", 0) or 0)))
                return lat, lon, f"Approximate {kind}: {place}", confidence, "approximate_place"
        return None

    def _write_context_board(self, records: list[EvidenceRecord]) -> Path:
        rows = []
        for record in records:
            if not (getattr(record, "map_intelligence_confidence", 0) > 0 or getattr(record, "route_overlay_detected", False) or getattr(record, "detected_map_context", "").startswith("Map")):
                continue
            plan = "".join(f"<li>{html.escape(str(item))}</li>" for item in (getattr(record, "map_extraction_plan", []) or getattr(record, "map_recommended_actions", []) or [])[:5]) or "<li>Run map_deep OCR/manual crop OCR to extract labels or coordinates.</li>"
            rows.append(
                f"""
                <div class='card'>
                    <h2>{html.escape(record.evidence_id)} — {html.escape(record.file_name)}</h2>
                    <div class='pill-row'>
                        <span class='pill'>Type: {html.escape(getattr(record, 'map_type', 'Unknown'))}</span>
                        <span class='pill'>App: {html.escape(getattr(record, 'map_app_detected', 'Unknown'))}</span>
                        <span class='pill'>Readiness: {html.escape(getattr(record, 'map_answer_readiness_label', 'Not answer-ready'))} ({getattr(record, 'map_answer_readiness_score', 0)}%)</span>
                        <span class='pill'>Route: {'yes' if getattr(record, 'route_overlay_detected', False) else 'no'} ({getattr(record, 'route_confidence', 0)}%)</span>
                    </div>
                    <p><b>Context:</b> {html.escape(getattr(record, 'detected_map_context', 'Unavailable'))}</p>
                    <p><b>Candidate place:</b> {html.escape(getattr(record, 'possible_place', 'Unavailable'))}</p>
                    <p><b>Anchor status:</b> {html.escape(getattr(record, 'map_anchor_status', 'No stable map/location anchor recovered.'))}</p>
                    <p><b>Evidence basis:</b> {html.escape(', '.join(getattr(record, 'map_evidence_basis', []) or []) or 'none')}</p>
                    <h3>Extraction plan</h3><ul>{plan}</ul>
                </div>
                """
            )
        body = "".join(rows) or "<div class='card'><h2>No map context available</h2><p>Import evidence with GPS, coordinates, OCR labels, map URLs, or visual map context.</p></div>"
        output = self.export_dir / "map_intelligence_board.html"
        output.write_text(
            f"""
            <!doctype html><html><head><meta charset='utf-8'><title>GeoTrace Map Intelligence Board</title>
            <style>
            body{{margin:0;background:#03111d;color:#e8f5ff;font-family:Segoe UI,Arial,sans-serif;padding:28px;}}
            .hero,.card{{background:#071525;border:1px solid #173c63;border-radius:22px;padding:22px;margin-bottom:18px;}}
            .muted{{color:#9ebed7}} .pill-row{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}}
            .pill{{background:#10243f;border:1px solid #27547f;border-radius:999px;padding:6px 11px;color:#dff5ff;font-size:13px}}
            li{{line-height:1.7}}
            </style></head><body>
            <section class='hero'><h1>GeoTrace Map Intelligence Board</h1><p class='muted'>No exact coordinate anchor was available. This board shows map type, anchor readiness, and what must be extracted before plotting a real place.</p></section>
            {body}
            </body></html>
            """.strip(),
            encoding="utf-8",
        )
        return output

    def create_map(self, records: Iterable[EvidenceRecord]) -> Path | None:
        all_records = list(records)
        point_rows: list[tuple[EvidenceRecord, float, float, str, int, str]] = []
        for record in all_records:
            point = self._geo_point_for_record(record)
            if point is not None:
                lat, lon, source, confidence, anchor_kind = point
                point_rows.append((record, lat, lon, source, confidence, anchor_kind))
        if not point_rows:
            context_records = [record for record in all_records if getattr(record, "map_intelligence_confidence", 0) > 0 or getattr(record, "route_overlay_detected", False)]
            if context_records:
                return self._write_context_board(context_records)
            return None

        ordered_records = sorted(point_rows, key=lambda row: (parse_timestamp(row[0].timestamp) is None, parse_timestamp(row[0].timestamp) or row[0].timestamp, row[0].evidence_id))
        center_lat = sum(row[1] for row in ordered_records) / len(ordered_records)
        center_lon = sum(row[2] for row in ordered_records) / len(ordered_records)
        evidence_map = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
        folium.TileLayer("CartoDB dark_matter", name="Dark").add_to(evidence_map)
        folium.TileLayer("CartoDB positron", name="Light").add_to(evidence_map)
        folium.TileLayer("OpenStreetMap", name="Road").add_to(evidence_map)

        points = []
        risk_colors = {"High": "red", "Medium": "orange", "Low": "blue"}
        for idx, (record, latitude, longitude, point_source, point_confidence, anchor_kind) in enumerate(ordered_records, start=1):
            points.append([latitude, longitude])
            safe_file = html.escape(record.file_name)
            safe_evidence_id = html.escape(record.evidence_id)
            safe_timestamp = html.escape(record.timestamp)
            safe_timestamp_source = html.escape(record.timestamp_source)
            safe_risk = html.escape(record.risk_level)
            safe_value_label = html.escape(record.evidentiary_label)
            safe_device = html.escape(record.device_model)
            safe_source = html.escape(record.source_type)
            safe_gps = html.escape(record.gps_display)
            safe_derived_geo = html.escape(record.derived_geo_display)
            safe_point_source = html.escape(point_source)
            policy = claim_policy_for_anchor(anchor_kind_from_source(point_source, has_native_gps=anchor_kind == "native_gps", has_coordinates=True), confidence=point_confidence, source=point_source)
            exact_anchor = anchor_kind in {"native_gps", "derived_coordinate"}
            safe_claim_label = html.escape(policy.claim_label)
            safe_proof_level = html.escape(policy.proof_level)
            safe_rule = html.escape(policy.verification_rule)
            safe_map_type = html.escape(getattr(record, "map_type", "Unknown"))
            safe_answer = html.escape(getattr(record, "map_answer_readiness_label", "Not answer-ready"))
            safe_sha = html.escape(f"{record.sha256[:16]}…{record.sha256[-12:]}")
            popup_html = f"""
            <div style='font-family:Segoe UI,Arial,sans-serif;min-width:290px;'>
                <h4 style='margin:0 0 8px 0;'>#{idx:02d} • {safe_evidence_id}</h4>
                <b>File:</b> {safe_file}<br>
                <b>Point source:</b> {safe_point_source}<br>
                <b>Claim type:</b> {safe_claim_label} • {safe_proof_level}<br>
                <b>Anchor:</b> {'Coordinate anchor' if exact_anchor else 'Approximate place lead'} • {point_confidence}%<br>
                <b>Verification:</b> {safe_rule}<br>
                <b>Map type:</b> {safe_map_type}<br>
                <b>Answer readiness:</b> {safe_answer} ({getattr(record, 'map_answer_readiness_score', 0)}%)<br>
                <b>Time:</b> {safe_timestamp} ({safe_timestamp_source}, {record.timestamp_confidence}%)<br>
                <b>Risk / Score:</b> {safe_risk} ({record.suspicion_score})<br>
                <b>Evidence value:</b> {record.evidentiary_value}% ({safe_value_label})<br>
                <b>Device:</b> {safe_device}<br>
                <b>Source:</b> {safe_source}<br>
                <b>Native GPS:</b> {safe_gps}<br>
                <b>Derived Geo:</b> {safe_derived_geo}<br>
                <b>SHA-256:</b> {safe_sha}
            </div>
            """
            folium.Marker(
                [latitude, longitude],
                popup=popup_html,
                tooltip=f"#{idx:02d} • {safe_evidence_id} • {point_source}",
                icon=folium.Icon(color="green" if anchor_kind == "native_gps" else "cadetblue" if anchor_kind == "derived_coordinate" else "purple", icon="camera" if record.has_gps else "map-pin", prefix="fa"),
            ).add_to(evidence_map)
            confidence_radius = policy.radius_m or (55 + point_confidence * 3.1)
            folium.Circle(
                location=[latitude, longitude],
                radius=confidence_radius,
                color="#00d084" if anchor_kind == "native_gps" else "#38d8ff" if anchor_kind == "derived_coordinate" else "#b48cff",
                fill=True,
                fill_opacity=0.12,
                weight=2,
                tooltip=f"{policy.claim_label} • confidence {point_confidence}% • radius ~{int(confidence_radius)}m",
            ).add_to(evidence_map)

        if len(points) > 1:
            folium.PolyLine(points, weight=3, color="#00d5ff", opacity=0.75, tooltip="Chronology path").add_to(evidence_map)
            evidence_map.fit_bounds(points, padding=(25, 25))
        else:
            evidence_map.location = points[0]
            evidence_map.zoom_start = 12

        legend = """
        <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999; background: rgba(7,17,27,0.92); color: #eaf7ff; border: 1px solid #1b4c71; border-radius: 12px; padding: 12px 14px; min-width: 250px; font-family: Segoe UI, Arial, sans-serif; font-size: 13px; box-shadow: 0 12px 30px rgba(0,0,0,0.28);">
            <div style="font-weight:700; margin-bottom:6px;">GeoTrace map intelligence</div>
            <div>Green halo = Native GPS metadata anchor.</div>
            <div>Blue halo = Derived Geo Anchor from visible map/OCR/URL coordinates.</div>
            <div>Purple halo = approximate Map Search Lead.</div>
            <div style="margin-top:6px;">Approximate leads use broad radii and require manual corroboration before reporting as a final location.</div>
        </div>
        """
        evidence_map.get_root().html.add_child(folium.Element(legend))
        folium.LayerControl().add_to(evidence_map)
        output = self.export_dir / "geolocation_map.html"
        evidence_map.save(str(output))
        return output
