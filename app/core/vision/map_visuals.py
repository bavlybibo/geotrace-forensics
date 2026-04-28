from __future__ import annotations

"""Visual map-signal helpers.

This module is the new home for lightweight, deterministic image heuristics used
by Map Intelligence. The scoring intentionally stays conservative: visual colour
patterns can create a lead, but never a courtroom location fact without OCR, URL,
or native GPS corroboration.
"""

from pathlib import Path
from typing import Iterable
import logging

from PIL import Image, ImageFilter

LOGGER = logging.getLogger("geotrace.vision.map_visuals")


def _unique(items: Iterable[str], limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def classify_visual_map_profile(file_path: Path) -> dict[str, object]:
    """Classify map-like visual style without claiming a real-world place.

    This is deliberately deterministic and offline. It answers: "what kind of
    map/screenshot does this look like?" not "where is it?". Place extraction is
    handled later by OCR, visible coordinates, map URLs, GPS, and analyst review.
    """
    metrics: dict[str, float] = {}
    reasons: list[str] = []
    try:
        with Image.open(file_path) as img:
            rgb = img.convert("RGB")
            thumb = rgb.resize((160, 160))
            gray = thumb.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            pixels = list(thumb.getdata())
            edge_pixels = list(edges.getdata())
    except Exception as exc:  # pragma: no cover - depends on corrupted external inputs
        LOGGER.debug("Could not classify visual map profile for %s: %s", file_path, exc)
        return {
            "map_score": 0,
            "route_score": 0,
            "map_type": "Unknown",
            "style": "Unknown",
            "provider_hint": "Unknown",
            "anchor_status": "No visual map profile",
            "place_extractability": "No visual map signal",
            "reasons": [],
            "metrics": {},
        }

    total = max(1, len(pixels))
    light_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 >= 182) / total
    dark_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 <= 72) / total
    white_ui_ratio = sum(1 for r, g, b in pixels if r >= 218 and g >= 218 and b >= 210) / total
    green_ratio = sum(1 for r, g, b in pixels if g >= 120 and g >= r + 8 and g >= b - 10) / total
    water_blue_ratio = sum(1 for r, g, b in pixels if 90 <= r <= 190 and 110 <= g <= 195 and b >= 140 and b >= r + 8) / total
    road_yellow_ratio = sum(1 for r, g, b in pixels if r >= 190 and g >= 150 and 35 <= b <= 135) / total
    road_orange_ratio = sum(1 for r, g, b in pixels if r >= 180 and 80 <= g <= 160 and b <= 110) / total
    route_blue_ratio = sum(1 for r, g, b in pixels if b >= 145 and g <= 130 and r <= 145 and b >= r + 35) / total
    route_purple_ratio = sum(1 for r, g, b in pixels if b >= 120 and r >= 65 and g <= 120 and (b + r) >= 205) / total
    pin_red_ratio = sum(1 for r, g, b in pixels if r >= 175 and g <= 105 and b <= 115) / total
    transit_multicolor_ratio = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) >= 105 and (r >= 160 or g >= 160 or b >= 160)) / total
    edge_density = sum(1 for value in edge_pixels if value >= 42) / max(1, len(edge_pixels))
    colorfulness = sum(max(r, g, b) - min(r, g, b) for r, g, b in pixels) / total

    metrics.update(
        {
            "light_ratio": round(light_ratio, 4),
            "dark_ratio": round(dark_ratio, 4),
            "white_ui_ratio": round(white_ui_ratio, 4),
            "green_ratio": round(green_ratio, 4),
            "water_blue_ratio": round(water_blue_ratio, 4),
            "road_yellow_ratio": round(road_yellow_ratio, 4),
            "road_orange_ratio": round(road_orange_ratio, 4),
            "route_blue_ratio": round(route_blue_ratio, 4),
            "route_purple_ratio": round(route_purple_ratio, 4),
            "pin_red_ratio": round(pin_red_ratio, 4),
            "transit_multicolor_ratio": round(transit_multicolor_ratio, 4),
            "edge_density": round(edge_density, 4),
            "colorfulness_proxy": round(colorfulness, 2),
        }
    )

    map_score = 0
    if light_ratio >= 0.40:
        map_score += 26
        reasons.append("light tiled-map canvas detected")
    if white_ui_ratio >= 0.28:
        map_score += 10
        reasons.append("large white/light UI map canvas")
    if water_blue_ratio >= 0.035:
        map_score += 15
        reasons.append("water/road-blue map styling detected")
    if green_ratio >= 0.035:
        map_score += 14
        reasons.append("park/green map regions detected")
    if road_yellow_ratio >= 0.010 or road_orange_ratio >= 0.008:
        map_score += 10
        reasons.append("road/highway color accents detected")
    if pin_red_ratio >= 0.001:
        map_score += 6
        reasons.append("red marker/POI-like pixels detected")
    if dark_ratio >= 0.35 and edge_density >= 0.055:
        map_score += 16
        reasons.append("dark map/navigation canvas with line detail detected")

    route_ratio = route_blue_ratio + route_purple_ratio
    route_score = 0
    if route_ratio >= 0.003:
        route_score += 54
        reasons.append("blue/purple route-overlay pixels detected")
    if route_ratio >= 0.008:
        route_score += 20
        reasons.append("route overlay appears visually prominent")
    if pin_red_ratio >= 0.001:
        route_score += 8
        reasons.append("possible route endpoint marker detected")

    # Style/type classification: useful for UI/reporting, not proof of location.
    if route_score >= 58:
        map_type = "Route / navigation map"
        style = "route overlay"
    elif dark_ratio >= 0.35 and edge_density >= 0.055:
        map_type = "Dark road/navigation map"
        style = "dark map"
    elif edge_density >= 0.145 and colorfulness >= 45 and green_ratio >= 0.09 and white_ui_ratio < 0.42:
        map_type = "Satellite / terrain-like map"
        style = "satellite/terrain"
        reasons.append("high texture/color variation resembles satellite or terrain imagery")
    elif transit_multicolor_ratio >= 0.09 and edge_density >= 0.06:
        map_type = "Transit / multi-line map"
        style = "transit-like"
        reasons.append("multi-color line density resembles transit or route-layer map")
    elif map_score >= 35:
        map_type = "Road / tiled map canvas"
        style = "road map"
    else:
        map_type = "Unknown"
        style = "No reliable visual map type"

    provider_hint = "Google Maps-like UI" if light_ratio >= 0.45 and (green_ratio >= 0.035 or water_blue_ratio >= 0.025) else "Unknown"
    anchor_status = "Visual context only — place not extractable without OCR/URL/GPS"
    place_extractability = "Need OCR labels, visible coordinates, share URL, GPS, or landmark corroboration"

    return {
        "map_score": min(95, int(map_score)),
        "route_score": min(95, int(route_score)),
        "map_type": map_type,
        "style": style,
        "provider_hint": provider_hint,
        "anchor_status": anchor_status,
        "place_extractability": place_extractability,
        "reasons": _unique(reasons, limit=8),
        "metrics": metrics,
    }


def score_visual_map_and_route(file_path: Path) -> tuple[int, int, list[str]]:
    """Return conservative (map_score, route_score, reasons) for a still image."""
    profile = classify_visual_map_profile(file_path)
    return int(profile.get("map_score", 0) or 0), int(profile.get("route_score", 0) or 0), list(profile.get("reasons", []) or [])


def summarize_visual_map_signals(basis: Iterable[str], *, confidence: int = 0) -> str:
    basis_set = {str(item) for item in basis if item}
    if not basis_set:
        return "No visual map signal was recorded."
    if basis_set == {"filename"}:
        return "Filename-only map hint; keep as weak signal."
    if "route-visual" in basis_set or "visual-map-colors" in basis_set or "map-visual" in basis_set:
        return f"Visual map evidence present ({confidence}%). Treat as lead only when OCR/URL/GPS corroborates it."
    return f"Map-related basis: {', '.join(sorted(basis_set))}."
