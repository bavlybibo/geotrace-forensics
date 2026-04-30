from __future__ import annotations

"""Internal map workspace payloads for the UI and exports."""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .map_reconstruction import build_map_reconstruction
from .models import EvidenceRecord
from .map.evidence import anchor_kind_from_source, claim_policy_for_anchor
from .map.geo_confidence import build_case_geo_ladders
from .map.ocr_zones import build_case_map_ocr_zones
from .map.preview import render_internal_map_preview_html


@dataclass(slots=True)
class MapWorkspaceBundle:
    summary: dict[str, Any]
    source_comparison: list[str] = field(default_factory=list)
    provider_bridge: list[str] = field(default_factory=list)
    provider_links: list[dict[str, Any]] = field(default_factory=list)
    candidate_cards: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    geo_ladders: list[dict[str, Any]] = field(default_factory=list)
    ocr_zones: list[dict[str, Any]] = field(default_factory=list)
    internal_map_preview_html: str = ""
    evidence_graph_cards: list[dict[str, Any]] = field(default_factory=list)
    privacy_note: str = 'Local/offline workspace. Do not send evidence or coordinates to third-party maps unless the analyst approves.'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bridge_lines(bridge: dict[str, Any]) -> list[str]:
    lines = [
        f"Bridge status: {bridge.get('status', 'unknown')}",
        f"Anchor source: {bridge.get('anchor_source', 'Unavailable')}",
        f"Anchor label: {bridge.get('anchor_label', 'Unavailable')}",
    ]
    lat = bridge.get('latitude')
    lon = bridge.get('longitude')
    if lat is not None and lon is not None:
        lines.append(f"Coordinates: {lat}, {lon}")
    if bridge.get('reverse_lookup_label') not in {None, '', 'Unavailable'}:
        lines.append(f"Reverse lookup: {bridge.get('reverse_lookup_label')} ({bridge.get('reverse_lookup_confidence', 0)}%)")
    queries = bridge.get('search_queries') if isinstance(bridge.get('search_queries'), list) else []
    if queries:
        lines.append('Search queries: ' + ' | '.join(str(q) for q in queries[:4]))
    links = bridge.get('provider_links') if isinstance(bridge.get('provider_links'), list) else []
    if links:
        lines.append(f"Provider links ready: {len(links)}")
    warnings = bridge.get('warnings') if isinstance(bridge.get('warnings'), list) else []
    lines.extend(str(warning) for warning in warnings[:3])
    return lines


def _local_vision_provider(record: EvidenceRecord) -> str:
    metrics = getattr(record, 'image_detail_metrics', {}) or {}
    if not isinstance(metrics, dict):
        return 'not executed'
    local_vision = metrics.get('local_vision', {})
    if isinstance(local_vision, dict) and local_vision.get('executed'):
        return str(local_vision.get('provider', 'local vision'))
    if isinstance(local_vision, dict) and local_vision.get('available'):
        return 'configured-not-executed'
    return 'not executed'


def build_map_workspace_bundle(records: Iterable[EvidenceRecord]) -> MapWorkspaceBundle:
    rows = list(records)
    reconstruction = build_map_reconstruction(rows)
    source_comparison: list[str] = []
    provider_bridge: list[str] = []
    provider_links: list[dict[str, Any]] = []
    candidate_cards: list[dict[str, Any]] = []
    for record in rows:
        comparison = getattr(record, 'map_source_comparison', []) or []
        if comparison:
            source_comparison.extend([f"{record.evidence_id}: {item}" for item in comparison[:5]])
        bridge = getattr(record, 'map_provider_bridge', {}) or {}
        if isinstance(bridge, dict) and bridge:
            provider_bridge.extend([f"{record.evidence_id}: {line}" for line in _bridge_lines(bridge)[:8]])
        for link in getattr(record, 'map_provider_links', []) or []:
            if isinstance(link, dict):
                provider_links.append({'evidence_id': record.evidence_id, **link})
        candidates = getattr(record, 'geo_candidates', []) or getattr(record, 'ctf_landmark_matches', []) or getattr(record, 'map_offline_geocoder_hits', []) or []
        for candidate in candidates[:4]:
            if isinstance(candidate, dict):
                candidate_cards.append({
                    'evidence_id': record.evidence_id,
                    'name': candidate.get('name') or candidate.get('label') or candidate.get('city') or 'Candidate',
                    'confidence': candidate.get('confidence') or candidate.get('score') or 0,
                    'basis': candidate.get('basis') or candidate.get('source') or candidate.get('reasons') or [],
                })

    geo_ladders = build_case_geo_ladders(rows)
    ocr_zones = build_case_map_ocr_zones(rows)
    evidence_graph_cards: list[dict[str, Any]] = []
    for record in rows[:16]:
        ladder = next((item for item in geo_ladders if item.get('evidence_id') == record.evidence_id), {})
        bridge = getattr(record, 'map_provider_bridge', {}) or {}
        anchor_source = bridge.get('anchor_source') if isinstance(bridge, dict) else ''
        has_coord = bool(isinstance(bridge, dict) and bridge.get('latitude') is not None and bridge.get('longitude') is not None)
        anchor_kind = anchor_kind_from_source(anchor_source or getattr(record, 'derived_geo_source', '') or getattr(record, 'map_anchor_status', ''), has_native_gps=bool(getattr(record, 'has_gps', False)), has_coordinates=has_coord or getattr(record, 'derived_latitude', None) is not None)
        policy = claim_policy_for_anchor(anchor_kind, confidence=int(ladder.get('final_score', 0) or 0), source=anchor_source or getattr(record, 'derived_geo_source', ''))
        evidence_graph_cards.append({
            'evidence_id': record.evidence_id,
            'native_gps': 'present' if getattr(record, 'has_gps', False) else 'missing',
            'derived_geo': getattr(record, 'derived_geo_display', 'Unavailable'),
            'map_mode': 'active' if getattr(record, 'map_intelligence_confidence', 0) else 'inactive',
            'provider_bridge': getattr(record, 'map_bridge_status', 'not_evaluated'),
            'local_vision': _local_vision_provider(record),
            'classification': ladder.get('primary_classification', 'No Geo Anchor'),
            'score': ladder.get('final_score', 0),
            'posture': ladder.get('final_posture', ''),
            'anchor_kind': policy.anchor_kind,
            'claim_label': policy.claim_label,
            'proof_level': policy.proof_level,
            'radius_m': policy.radius_m,
            'report_wording': policy.report_wording,
            'verification_rule': policy.verification_rule,
        })

    next_actions = [
        'Validate derived coordinates against a preserved map URL, source-app history, upload context, or witness timeline.',
        'Use Map Screenshot Mode OCR zones: search bar, route card, pin/context menu, visible labels, and corners.',
        'Treat route reconstruction as provisional until at least two independent anchors agree.',
        'Keep Native GPS, Derived Geo Anchor, and Map Search Lead as separate report claims.',
    ]
    if not reconstruction.anchor_count:
        next_actions.insert(0, 'No anchor yet: crop visible labels, inspect OCR output, and collect surrounding chat/cloud/browser context.')
    return MapWorkspaceBundle(
        summary=reconstruction.to_dict(),
        source_comparison=source_comparison[:30],
        provider_bridge=provider_bridge[:40],
        provider_links=provider_links[:24],
        candidate_cards=candidate_cards[:24],
        next_actions=next_actions,
        geo_ladders=geo_ladders[:24],
        ocr_zones=ocr_zones[:40],
        internal_map_preview_html=render_internal_map_preview_html(reconstruction.to_dict().get('anchors', []) or []),
        evidence_graph_cards=evidence_graph_cards[:24],
    )


def render_map_workspace_markdown(records: Iterable[EvidenceRecord]) -> str:
    bundle = build_map_workspace_bundle(records)
    summary = bundle.summary
    lines = [
        '# Internal Map Workspace',
        '',
        f"Anchors: {summary.get('anchor_count', 0)} | Native GPS: {summary.get('native_gps_count', 0)} | Derived: {summary.get('derived_count', 0)}",
        f"Story: {summary.get('route_story', 'No route story generated.')}",
    ]
    if summary.get('centroid'):
        c = summary['centroid']
        lines.append(f"Centroid: {c.get('latitude')}, {c.get('longitude')}")
    lines.extend(['', '## Anchors'])
    for anchor in summary.get('anchors', []) or []:
        lines.append(f"- {anchor.get('evidence_id')} — {anchor.get('latitude')}, {anchor.get('longitude')} | {anchor.get('source')} | confidence {anchor.get('confidence')}% | radius ~{anchor.get('radius_m')}m")
    if not summary.get('anchors'):
        lines.append('- No coordinate anchors available.')
    if summary.get('anomalies'):
        lines.extend(['', '## Anomalies'])
        lines.extend(f"- {item}" for item in summary.get('anomalies', []))
    if summary.get('limitations'):
        lines.extend(['', '## Limitations'])
        lines.extend(f"- {item}" for item in summary.get('limitations', []))
    lines.extend(['', '## Source Comparison'])
    lines.extend(f"- {item}" for item in (bundle.source_comparison or ['No cross-source comparison rows yet.']))
    lines.extend(['', '## External Map Bridge'])
    lines.extend(f"- {item}" for item in (bundle.provider_bridge or ['No provider bridge rows yet.']))
    if bundle.provider_links:
        lines.extend(['', '## Provider Verification Links'])
        for link in bundle.provider_links[:10]:
            lines.append(f"- {link.get('evidence_id')} • {link.get('provider')} • {link.get('kind')}: {link.get('url')}")
    lines.extend(['', '## Geo Confidence Ladder'])
    for item in bundle.geo_ladders[:10]:
        lines.append(f"- {item.get('evidence_id')} • {item.get('primary_classification')} • {item.get('final_score')}% — {item.get('final_posture')}")
    lines.extend(['', '## Evidence Graph Claim Cards'])
    for card in bundle.evidence_graph_cards[:10]:
        lines.append(f"- {card.get('evidence_id')} • {card.get('claim_label')} • {card.get('proof_level')} • radius ~{card.get('radius_m')}m — {card.get('verification_rule')}")
    lines.extend(['', '## Map OCR Zones'])
    for zone in bundle.ocr_zones[:12]:
        lines.append(f"- {zone.get('evidence_id')} • P{zone.get('priority')} • {zone.get('zone')} — {zone.get('expected_signal')}")
    lines.extend(['', '## Next Actions'])
    lines.extend(f"- {item}" for item in bundle.next_actions)
    lines.extend(['', f"Privacy note: {bundle.privacy_note}"])
    return '\n'.join(lines).strip() + '\n'
