from __future__ import annotations

"""Deterministic AI Guardian helpers for relationships, readiness, contradictions, and privacy audits."""

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional
from ..models import EvidenceRecord
from .features import haversine_km, record_coordinates, timeline_points
from .privacy_guardian import audit_records

@dataclass(frozen=True)
class EvidenceGraphEdge:
    source_id: str
    target_id: str
    relation: str
    weight: int
    reason: str
    def to_dict(self) -> dict:
        return asdict(self)

def _clean(text: str) -> str:
    return " ".join(str(text or "").split())

def build_evidence_graph(records: Iterable[EvidenceRecord]) -> List[EvidenceGraphEdge]:
    records_list = list(records)
    edges: List[EvidenceGraphEdge] = []
    def add(left: EvidenceRecord, right: EvidenceRecord, relation: str, weight: int, reason: str) -> None:
        if left.evidence_id == right.evidence_id:
            return
        a, b = sorted([left.evidence_id, right.evidence_id])
        edge = EvidenceGraphEdge(a, b, relation, max(1, min(100, weight)), _clean(reason))
        if edge not in edges:
            edges.append(edge)
    groups: Dict[str, List[EvidenceRecord]] = {}
    for r in records_list:
        if r.duplicate_group:
            groups.setdefault(r.duplicate_group, []).append(r)
    for gid, group in groups.items():
        for i, left in enumerate(group):
            for right in group[i+1:]:
                add(left, right, "duplicate_group", 96, f"Both items are in duplicate group {gid}; compare metadata context before treating either as original.")
    by_device: Dict[str, List[EvidenceRecord]] = {}
    for r in records_list:
        device = (r.device_model or "").strip()
        if device and device not in {"Unknown", "N/A", "Unavailable"}:
            by_device.setdefault(device, []).append(r)
    for device, group in by_device.items():
        for i, left in enumerate(group[:8]):
            for right in group[i+1:8]:
                add(left, right, "same_device", 58, f"Both items claim the same device model ({device}); use as provenance linkage, not authorship proof.")
    geo = [(r, record_coordinates(r)) for r in records_list]
    geo = [(r, p) for r, p in geo if p is not None]
    for i, (left, lp) in enumerate(geo):
        if lp is None:
            continue
        for right, rp in geo[i+1:]:
            if rp is None:
                continue
            lat1, lon1, s1, _ = lp
            lat2, lon2, s2, _ = rp
            d = haversine_km(lat1, lon1, lat2, lon2)
            if d <= 0.25:
                add(left, right, "same_location", 74, f"Location anchors are within {d:.2f} km ({s1} ↔ {s2}).")
            elif d <= 3:
                add(left, right, "nearby_location", 52, f"Location anchors are close ({d:.1f} km apart); verify whether this is the same activity cluster.")
    by_id = {r.evidence_id: r for r in records_list}
    for r in records_list:
        for link in r.ai_case_links:
            for peer_id, peer in by_id.items():
                if peer_id != r.evidence_id and peer_id in link:
                    add(r, peer, "ai_case_link", 65, link)
    return sorted(edges, key=lambda e: (-e.weight, e.relation, e.source_id, e.target_id))[:120]

def explain_contradictions(records: Iterable[EvidenceRecord]) -> List[str]:
    points = timeline_points(list(records))
    out: List[str] = []
    for prev, cur in zip(points, points[1:]):
        hours = (cur.timestamp - prev.timestamp).total_seconds() / 3600
        d = haversine_km(prev.latitude, prev.longitude, cur.latitude, cur.longitude)
        if d < 25:
            continue
        speed = float('inf') if hours <= 0 else d / max(hours, 0.0001)
        if hours <= 0 or speed >= 220:
            speed_text = "not computable because the second timestamp is not later" if hours <= 0 else f"{speed:.0f} km/h"
            out.append(
                "Why this is suspicious: "
                f"{prev.record.evidence_id} claims {prev.source} at {prev.timestamp.strftime('%Y-%m-%d %H:%M')} and "
                f"{cur.record.evidence_id} claims {cur.source} at {cur.timestamp.strftime('%Y-%m-%d %H:%M')}. "
                f"Distance: {d:.1f} km. Required speed: {speed_text}. "
                "Conclusion: timeline/location conflict requires manual verification before it appears in the final narrative."
            )
    return out[:20]

def courtroom_readiness(record: EvidenceRecord) -> tuple[bool, List[str]]:
    reasons: List[str] = []
    if record.parser_status != "Valid": reasons.append("Parser did not fully validate the media container")
    if record.signature_status == "Mismatch": reasons.append("File extension/signature mismatch needs secondary validation")
    if record.integrity_status not in {"Verified", "Partial"}: reasons.append("Integrity status is not strong enough yet")
    if record.timestamp_confidence < 70: reasons.append("No strong independent timestamp anchor")
    if not record.has_gps and record.derived_geo_confidence > 0: reasons.append("Derived location only; not native GPS")
    elif not record.has_gps and record.derived_geo_confidence == 0: reasons.append("No reliable location anchor")
    if record.ocr_confidence and record.ocr_confidence < 55: reasons.append("OCR confidence is weak")
    if record.time_conflicts: reasons.append("Conflicting time candidates require manual resolution")
    if record.ai_flags: reasons.append("AI batch review flagged this item for analyst confirmation")
    ready = record.courtroom_strength >= 68 and len(reasons) <= 2 and record.parser_status == "Valid" and record.signature_status != "Mismatch"
    return ready, (["Strong enough for courtroom-oriented summary after analyst review"] if ready else reasons[:8])

def next_best_action(record: EvidenceRecord) -> str:
    if record.ai_action_plan: return record.ai_action_plan[0]
    if record.parser_status != "Valid" or record.signature_status == "Mismatch": return "Validate the file with a second parser before relying on extracted content or metadata."
    if record.time_conflicts or record.timestamp_confidence < 70: return "Verify timestamp from the original device, source app export, upload history, or chat logs before using this item in the final timeline."
    if record.has_gps: return "Verify the native GPS coordinate externally and compare it against adjacent evidence for travel plausibility."
    if getattr(record, "route_overlay_detected", False): return "Confirm the route in Google Maps/source history and document start/end assumptions before using it as movement evidence."
    if record.derived_geo_confidence > 0 or record.ocr_map_labels or record.possible_geo_clues or getattr(record, "map_intelligence_confidence", 0) > 0: return "Convert visible map/location clues into a corroborated location hypothesis using source app history, URLs, OCR labels, or manual map review."
    if record.duplicate_group: return "Open duplicate comparison and decide which peer is the original or most reliable source."
    return "Record an analyst note explaining why this item is useful, limited, or excluded from the final narrative."

def case_readiness_scores(records: Iterable[EvidenceRecord], *, custody_ok: Optional[bool] = None) -> dict:
    items = list(records); total = len(items)
    if not total:
        return {"case_readiness":0,"timeline_readiness":0,"location_readiness":0,"integrity_readiness":0,"privacy_readiness":100,"courtroom_readiness":0,"summary":"No evidence loaded yet."}
    timeline = round(sum(min(100, r.timestamp_confidence) for r in items)/total)
    loc_vals = [
        max(r.gps_confidence, 70) if r.has_gps
        else min(70, r.derived_geo_confidence) if r.derived_geo_confidence > 0
        else min(55, getattr(r, "map_confidence", 0)) if getattr(r, "map_confidence", 0) > 0
        else 0
        for r in items
    ]
    location = round(sum(loc_vals)/total)
    integ_vals=[]
    for r in items:
        if r.integrity_status == "Verified": integ_vals.append(95)
        elif r.integrity_status == "Partial": integ_vals.append(70)
        elif r.parser_status == "Valid" and r.signature_status != "Mismatch": integ_vals.append(55)
        else: integ_vals.append(25)
    integrity = round(sum(integ_vals)/total)
    if custody_ok is False: integrity = max(0, integrity-15)
    raw_text = sum(1 for r in items if r.ocr_raw_text or r.visible_urls or r.ocr_username_entities or r.visible_location_strings)
    privacy = max(45, 100 - raw_text*5)
    courtroom = round(sum(r.courtroom_strength for r in items)/total)
    overall = round(timeline*.20 + location*.18 + integrity*.24 + privacy*.13 + courtroom*.25)
    flagged = sum(1 for r in items if r.ai_flags)
    return {"case_readiness":overall,"timeline_readiness":timeline,"location_readiness":location,"integrity_readiness":integrity,"privacy_readiness":privacy,"courtroom_readiness":courtroom,"summary":f"Case Readiness: {overall}% | Timeline {timeline}% | Location {location}% | Integrity {integrity}% | Privacy {privacy}% | Courtroom {courtroom}% | AI flagged {flagged}/{total}."}

def privacy_audit_status(records: Iterable[EvidenceRecord], privacy_level: str="redacted_text") -> dict:
    items = list(records)
    strict = privacy_level in {"redacted_text", "courtroom_redacted"}
    audit = audit_records(items, privacy_level=privacy_level)
    coord = sum(1 for r in items if strict and (r.has_gps or (r.derived_latitude is not None and r.derived_longitude is not None)))
    ocr = sum(1 for r in items if strict and (r.ocr_raw_text or r.visible_text_lines or r.visible_urls))
    previews = not strict
    return {
        "status": audit.status,
        "privacy_level": privacy_level,
        "raw_filenames_found": len(items) if strict else 0,
        "coordinate_items": coord,
        "ocr_text_items": ocr,
        "preview_assets_included": previews,
        "issues": [issue.__dict__ for issue in audit.issues],
        "summary": audit.summary + f"\nCoordinate-bearing items requiring redaction: {coord}\nOCR/raw text items requiring redaction: {ocr}\nPreview assets included: {'Yes' if previews else 'No'}",
    }

def guardian_narrative(records: Iterable[EvidenceRecord], *, custody_ok: Optional[bool]=None, privacy_level: str="redacted_text") -> str:
    items=list(records); readiness=case_readiness_scores(items,custody_ok=custody_ok); graph=build_evidence_graph(items); contradictions=explain_contradictions(items); privacy=privacy_audit_status(items, privacy_level)
    top=sorted(items, key=lambda r:(-r.ai_score_delta,-r.suspicion_score,r.evidence_id))[:5]
    lines=[readiness['summary'], '', 'Top AI review queue:']
    if top:
        for r in top:
            ready,reasons=courtroom_readiness(r)
            lines.append(f"- {r.evidence_id}: {r.ai_risk_label} | Score {r.suspicion_score} | Courtroom {'Yes' if ready else 'No'} | Next: {next_best_action(r)}")
            if reasons: lines.append('  Reason: ' + '; '.join(reasons[:3]))
    else: lines.append('- No evidence loaded.')
    lines += ['', f'Evidence graph edges: {len(graph)}']
    lines += [f"- {e.source_id} ↔ {e.target_id} [{e.relation}, {e.weight}%]: {e.reason}" for e in graph[:8]] or ['- No relationship edges yet.']
    map_items = [r for r in items if getattr(r, "map_intelligence_confidence", 0) > 0 or getattr(r, "route_overlay_detected", False)]
    lines += ['', 'Map Intelligence:']
    if map_items:
        for r in sorted(map_items, key=lambda item: (-getattr(item, "map_intelligence_confidence", 0), item.evidence_id))[:5]:
            route = 'route detected' if getattr(r, "route_overlay_detected", False) else 'no route overlay'
            city = getattr(r, "candidate_city", "Unavailable")
            area = getattr(r, "candidate_area", "Unavailable")
            city_bits = []
            if city != 'Unavailable': city_bits.append(f'city {city}')
            if area != 'Unavailable': city_bits.append(f'area {area}')
            place = '; '.join(city_bits) if city_bits else 'no stable place/city yet'
            lines.append(f"- {r.evidence_id}: {getattr(r, 'map_app_detected', 'Unknown')} • {route} • confidence {getattr(r, 'map_intelligence_confidence', 0)}% • {place}")
            if getattr(r, 'landmarks_detected', []):
                lines.append('  Landmarks: ' + ', '.join(r.landmarks_detected[:4]))
    else:
        lines.append('- No map/navigation intelligence detected yet.')
    lines += ['', 'Contradiction explainer:']
    lines += [f'- {c}' for c in contradictions[:6]] or ['- No impossible-travel contradiction detected with current anchors.']
    lines += ['', 'AI Privacy Auditor:', privacy['summary']]
    return '\n'.join(lines)
