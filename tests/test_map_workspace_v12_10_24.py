from pathlib import Path

from app.core.map_workspace import build_map_workspace_bundle
from app.core.models import EvidenceRecord


def _record(**kwargs):
    base = dict(
        case_id="case",
        case_name="case",
        evidence_id="IMG-001",
        file_path=Path("map.png"),
        file_name="map.png",
        sha256="x",
        md5="y",
        perceptual_hash="z",
        file_size=10,
        imported_at="now",
    )
    base.update(kwargs)
    return EvidenceRecord(**base)


def test_map_workspace_has_preview_ladder_ocr_zones_and_graph():
    r = _record(
        derived_latitude=40.48168,
        derived_longitude=-3.21450,
        derived_geo_display="40.481680, -3.214500",
        derived_geo_source="visible coordinate text",
        derived_geo_confidence=86,
        map_intelligence_confidence=82,
        map_app_detected="Google Maps",
        map_type="Route / navigation map",
        route_overlay_detected=True,
        route_confidence=88,
        place_candidates=["Madrid"],
        map_provider_links=[{"provider": "Google Maps", "url": "https://example.test", "kind": "coordinate"}],
        map_bridge_status="coordinate_bridge_ready",
    )
    bundle = build_map_workspace_bundle([r])
    assert "svg" in bundle.internal_map_preview_html.lower()
    assert bundle.geo_ladders[0]["primary_classification"] == "Derived Geo Anchor"
    assert bundle.ocr_zones
    assert any("Route" in zone["zone"] for zone in bundle.ocr_zones)
    assert bundle.evidence_graph_cards[0]["classification"] == "Derived Geo Anchor"
