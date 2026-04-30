from __future__ import annotations

from html import escape
import webbrowser
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from ...core.map_workspace import build_map_workspace_bundle, render_map_workspace_markdown
    from ...core.vision.local_vision_model import detect_local_vision_model
except ImportError:  # pragma: no cover
    from app.core.map_workspace import build_map_workspace_bundle, render_map_workspace_markdown
    from app.core.vision.local_vision_model import detect_local_vision_model


def build_map_workspace_page(window) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    hero = window._shell(
        'Internal Map Workspace',
        QLabel('Coordinate anchors, internal map preview, map screenshot OCR zones, source comparison, confidence ladder, and local vision status stay inside the local workspace.'),
        'Use this page before claiming a location or route. Native GPS, Derived Geo Anchor, and Map Search Lead are kept separate.'
    )
    layout.addWidget(hero)

    action_row = QHBoxLayout()
    window.btn_refresh_map_workspace = QPushButton('Refresh Map Workspace')
    window.btn_refresh_map_workspace.clicked.connect(window.refresh_map_workspace)
    window.btn_open_review_from_map = QPushButton('Open Review')
    window.btn_open_review_from_map.clicked.connect(lambda: window._set_workspace_page('Review'))
    window.btn_open_provider_map = QPushButton('Open Provider Link')
    window.btn_open_provider_map.clicked.connect(lambda: _open_selected_provider_link(window))
    action_row.addWidget(window.btn_refresh_map_workspace)
    action_row.addWidget(window.btn_open_review_from_map)
    action_row.addWidget(window.btn_open_provider_map)
    action_row.addStretch(1)
    layout.addLayout(action_row)

    grid = QGridLayout()
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)
    window.map_workspace_preview_view = window._make_guardian_view('Internal offline map preview appears here.', 360)
    window.map_workspace_summary_view = window._make_guardian_view('Map workspace summary appears here.', 240)
    window.map_workspace_anchor_view = window._make_guardian_view('Anchor cards appear here.', 260)
    window.map_workspace_ladder_view = window._make_guardian_view('Geo confidence ladder appears here.', 260)
    window.map_workspace_ocr_zones_view = window._make_guardian_view('Map Screenshot Mode OCR zones appear here.', 260)
    window.map_workspace_evidence_graph_view = window._make_guardian_view('Map evidence graph cards appear here.', 240)
    window.map_workspace_comparison_view = window._make_guardian_view('Source comparison appears here.', 230)
    window.map_workspace_model_view = window._make_guardian_view('Local vision model status appears here.', 190)
    window.map_workspace_provider_bridge_view = window._make_guardian_view('External map bridge status appears here.', 220)
    window.map_workspace_provider_links_view = window._make_guardian_view('Provider verification links appear here.', 220)

    grid.addWidget(window._shell('Internal Map Preview', window.map_workspace_preview_view, 'Offline SVG preview: Native GPS vs Derived Geo Anchor with confidence circles.'), 0, 0, 1, 2)
    grid.addWidget(window._shell('Reconstruction Summary', window.map_workspace_summary_view, 'Centroid, bounds, route story, anomalies, and limitations.'), 1, 0)
    grid.addWidget(window._shell('Anchor Cards', window.map_workspace_anchor_view, 'Native GPS and derived map/OCR anchors with confidence and radius.'), 1, 1)
    grid.addWidget(window._shell('Geo Confidence Ladder', window.map_workspace_ladder_view, 'Strict source hierarchy: GPS ≠ derived coordinate ≠ place lead.'), 2, 0)
    grid.addWidget(window._shell('Map Screenshot Mode OCR Zones', window.map_workspace_ocr_zones_view, 'Crop search bars, route cards, pins, labels, and corners instead of OCRing the whole map only.'), 2, 1)
    grid.addWidget(window._shell('Map Evidence Graph', window.map_workspace_evidence_graph_view, 'Compact flow from Native GPS → Derived Geo → Provider Bridge → Local Vision.'), 3, 0)
    grid.addWidget(window._shell('Source Comparison', window.map_workspace_comparison_view, 'Native GPS vs derived coordinate vs OCR/place/landmark signals.'), 3, 1)
    grid.addWidget(window._shell('Optional Local Vision', window.map_workspace_model_view, 'No remote AI. Real local model runner status only if configured.'), 4, 0)
    grid.addWidget(window._shell('External Map Bridge', window.map_workspace_provider_bridge_view, 'Generates privacy-gated Google/OSM/Apple verification links from GPS, map URL, OCR coordinates, or place labels.'), 4, 1)
    grid.addWidget(window._shell('Provider Verification Links', window.map_workspace_provider_links_view, 'Open only after privacy approval; evidence is never uploaded automatically.'), 5, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    layout.addLayout(grid)
    layout.addStretch(1)
    return widget


def _format_provider_links(links: list[dict]) -> str:
    rows: list[str] = []
    for link in links[:16]:
        if not isinstance(link, dict):
            continue
        rows.append(
            f"{link.get('evidence_id', 'EV')} | {link.get('provider', 'Provider')} | {link.get('kind', 'link')}\n"
            f"{link.get('label', 'Map verification')}\n{link.get('url', '')}\n"
            f"Privacy: {link.get('privacy_note', 'Open only after approval.')}"
        )
    return "\n\n".join(rows) if rows else "No provider links yet. Import evidence with native GPS, visible coordinates, map URLs, or place labels."


def _open_selected_provider_link(window) -> None:
    record = None
    try:
        record = window.selected_record()
    except Exception:
        record = None
    links = list(getattr(record, 'map_provider_links', []) or []) if record else []
    if not links:
        for candidate in list(getattr(window.case_manager, 'records', []) or []):
            candidate_links = list(getattr(candidate, 'map_provider_links', []) or [])
            if candidate_links:
                record = candidate
                links = candidate_links
                break
    for link in links:
        if isinstance(link, dict) and link.get('url'):
            webbrowser.open(str(link['url']))
            return
    try:
        window.show_info(
            'No Provider Link Yet',
            'No map provider link is available yet. Run deep OCR/manual crop OCR or import evidence with GPS, coordinate text, map URL, or clear place labels.',
        )
    except Exception:
        pass


def _anchor_html(anchor: dict) -> str:
    source = str(anchor.get('source', 'unknown'))
    human_source = 'Native GPS' if source == 'native-gps' else 'Derived Geo Anchor'
    return (
        "<div style='border:1px solid #24445a;border-radius:12px;padding:10px;margin-bottom:8px;background:#0b1722;'>"
        f"<b>{escape(str(anchor.get('evidence_id', 'EV')))}</b> — {escape(str(anchor.get('latitude')))}, {escape(str(anchor.get('longitude')))}<br/>"
        f"Source: {escape(human_source)} | Confidence: {escape(str(anchor.get('confidence', 0)))}% | Radius: ~{escape(str(anchor.get('radius_m', 0)))}m<br/>"
        f"Label: {escape(str(anchor.get('label', '') or 'Unavailable'))}"
        "</div>"
    )


def _ladder_html(ladders: list[dict]) -> str:
    if not ladders:
        return "<p>No geo confidence ladder yet. Import evidence and refresh analysis.</p>"
    cards: list[str] = []
    for item in ladders[:12]:
        lines = "".join(f"<li>{escape(str(line))}</li>" for line in item.get('lines', [])[:6])
        blockers = "".join(f"<li>{escape(str(line))}</li>" for line in item.get('blockers', [])[:3])
        cards.append(
            "<div style='border:1px solid #24445a;border-radius:14px;padding:12px;margin-bottom:10px;background:#0b1722;'>"
            f"<div style='font-weight:900;color:#8de9ff;'>{escape(str(item.get('evidence_id','EV')))} • {escape(str(item.get('primary_classification','No Geo Anchor')))} • {escape(str(item.get('final_score',0)))}%</div>"
            f"<div style='margin-top:6px;color:#c9d7e6;'>{escape(str(item.get('final_posture','')))}</div>"
            f"<ol style='margin-top:8px;color:#d9ecf7;'>{lines}</ol>"
            + (f"<div style='color:#ffd166;font-weight:800;'>Blockers</div><ul style='color:#ffd9a0;'>{blockers}</ul>" if blockers else "")
            + "</div>"
        )
    return "".join(cards)


def _ocr_zones_html(zones: list[dict]) -> str:
    if not zones:
        return "<p>No Map Screenshot Mode zones yet. A zone plan appears when map/navigation context is detected.</p>"
    out: list[str] = []
    for zone in zones[:14]:
        out.append(
            "<div style='border:1px solid #24445a;border-radius:12px;padding:10px;margin-bottom:8px;background:#0a1520;'>"
            f"<b style='color:#8de9ff;'>{escape(str(zone.get('evidence_id','EV')))} • P{escape(str(zone.get('priority',0)))} • {escape(str(zone.get('zone','zone')))}</b><br/>"
            f"<span style='color:#c9d7e6;'>Expected: {escape(str(zone.get('expected_signal','signal')))}</span><br/>"
            f"<span style='color:#9fb2c7;'>Why: {escape(str(zone.get('reason','')))}</span><br/>"
            f"<span style='color:#ffd166;'>Action: {escape(str(zone.get('analyst_action','')))}</span>"
            "</div>"
        )
    return "".join(out)


def _evidence_graph_html(cards: list[dict]) -> str:
    if not cards:
        return "<p>No map evidence graph yet.</p>"
    rows: list[str] = []
    for card in cards[:12]:
        rows.append(
            "<div style='border:1px solid #24445a;border-radius:12px;padding:10px;margin-bottom:8px;background:#0b1722;'>"
            f"<b style='color:#8de9ff;'>{escape(str(card.get('evidence_id','EV')))} → {escape(str(card.get('classification','No Geo Anchor')))} ({escape(str(card.get('score',0)))}%)</b><br/>"
            f"Native GPS: {escape(str(card.get('native_gps','missing')))} | Derived: {escape(str(card.get('derived_geo','Unavailable')))}<br/>"
            f"Map mode: {escape(str(card.get('map_mode','inactive')))} | Bridge: {escape(str(card.get('provider_bridge','not_evaluated')))} | Local vision: {escape(str(card.get('local_vision','not executed')))}<br/>"
            f"<span style='color:#9fb2c7;'>{escape(str(card.get('posture','')))}</span>"
            "</div>"
        )
    return "".join(rows)


def refresh_map_workspace_page(window) -> None:
    records = list(getattr(window.case_manager, 'records', []))
    bundle = build_map_workspace_bundle(records)
    summary = bundle.summary
    if hasattr(window, 'map_workspace_preview_view'):
        window.map_workspace_preview_view.setHtml(bundle.internal_map_preview_html)
    if hasattr(window, 'map_workspace_summary_view'):
        window.map_workspace_summary_view.setPlainText(render_map_workspace_markdown(records))
    if hasattr(window, 'map_workspace_anchor_view'):
        anchors = summary.get('anchors', []) or []
        if anchors:
            window.map_workspace_anchor_view.setHtml(''.join(_anchor_html(anchor) for anchor in anchors))
        else:
            window.map_workspace_anchor_view.setPlainText('No coordinate anchors available yet. Use OCR crop review, map URL inspection, and metadata review.')
    if hasattr(window, 'map_workspace_ladder_view'):
        window.map_workspace_ladder_view.setHtml(_ladder_html(bundle.geo_ladders))
    if hasattr(window, 'map_workspace_ocr_zones_view'):
        window.map_workspace_ocr_zones_view.setHtml(_ocr_zones_html(bundle.ocr_zones))
    if hasattr(window, 'map_workspace_evidence_graph_view'):
        window.map_workspace_evidence_graph_view.setHtml(_evidence_graph_html(bundle.evidence_graph_cards))
    if hasattr(window, 'map_workspace_comparison_view'):
        window.map_workspace_comparison_view.setPlainText('\n'.join(bundle.source_comparison or ['No source comparison rows yet.']))
    if hasattr(window, 'map_workspace_provider_bridge_view'):
        window.map_workspace_provider_bridge_view.setPlainText('\n'.join(bundle.provider_bridge or ['No provider bridge rows yet.']))
    if hasattr(window, 'map_workspace_provider_links_view'):
        window.map_workspace_provider_links_view.setPlainText(_format_provider_links(bundle.provider_links))
    if hasattr(window, 'map_workspace_model_view'):
        status = detect_local_vision_model().to_dict()
        lines = [
            f"Enabled: {status.get('enabled')}",
            f"Path: {status.get('path') or 'not configured'}",
            f"Model type: {status.get('model_type')}",
            'Capabilities: ' + (', '.join(status.get('capabilities') or []) or 'none'),
            'Command configured: ' + str(status.get('command_configured')),
            'Timeout: ' + str(status.get('timeout_seconds')) + 's',
            'Warnings:',
        ]
        lines.extend(f"- {item}" for item in (status.get('warnings') or ['None']))
        window.map_workspace_model_view.setPlainText('\n'.join(lines))
