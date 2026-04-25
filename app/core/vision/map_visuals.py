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

from PIL import Image

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


def score_visual_map_and_route(file_path: Path) -> tuple[int, int, list[str]]:
    """Return conservative (map_score, route_score, reasons) for a still image.

    The function avoids OCR and does not infer a place. It only describes visual
    evidence such as light map canvas, road/water colours, green park regions,
    red markers, and blue/purple route overlays.
    """
    reasons: list[str] = []
    try:
        with Image.open(file_path) as img:
            rgb = img.convert("RGB").resize((128, 128))
            pixels = list(rgb.getdata())
    except Exception as exc:  # pragma: no cover - depends on corrupted external inputs
        LOGGER.debug("Could not score visual map signals for %s: %s", file_path, exc)
        return 0, 0, reasons

    total = max(1, len(pixels))
    light_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 >= 182) / total
    road_blue_ratio = sum(1 for r, g, b in pixels if 95 <= r <= 190 and 115 <= g <= 190 and b >= 145 and b >= r + 10) / total
    green_ratio = sum(1 for r, g, b in pixels if g >= 125 and g >= r + 10 and g >= b - 8) / total
    route_blue_ratio = sum(1 for r, g, b in pixels if b >= 150 and g <= 120 and r <= 130 and b >= r + 45) / total
    route_purple_ratio = sum(1 for r, g, b in pixels if b >= 125 and r >= 60 and g <= 105 and (b + r) >= 210) / total
    pin_red_ratio = sum(1 for r, g, b in pixels if r >= 180 and g <= 95 and b <= 105) / total

    map_score = 0
    if light_ratio >= 0.40:
        map_score += 26
        reasons.append("light tiled-map canvas detected")
    if road_blue_ratio >= 0.045:
        map_score += 16
        reasons.append("road/water styled map colors detected")
    if green_ratio >= 0.035:
        map_score += 12
        reasons.append("park/green map regions detected")
    if pin_red_ratio >= 0.001:
        map_score += 6
        reasons.append("red marker/POI-like pixels detected")

    route_score = 0
    route_ratio = route_blue_ratio + route_purple_ratio
    if route_ratio >= 0.003:
        route_score += 54
        reasons.append("blue/purple route-overlay pixels detected")
    if route_ratio >= 0.008:
        route_score += 20
        reasons.append("route overlay appears visually prominent")
    if pin_red_ratio >= 0.001:
        route_score += 8
        reasons.append("possible route endpoint marker detected")

    return min(95, map_score), min(95, route_score), _unique(reasons, limit=6)


def summarize_visual_map_signals(basis: Iterable[str], *, confidence: int = 0) -> str:
    basis_set = {str(item) for item in basis if item}
    if not basis_set:
        return "No visual map signal was recorded."
    if basis_set == {"filename"}:
        return "Filename-only map hint; keep as weak signal."
    if "route-visual" in basis_set or "visual-map-colors" in basis_set or "map-visual" in basis_set:
        return f"Visual map evidence present ({confidence}%). Treat as lead only when OCR/URL/GPS corroborates it."
    return f"Map-related basis: {', '.join(sorted(basis_set))}."
