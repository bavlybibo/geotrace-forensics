from __future__ import annotations

"""Offline CTF visual clue engine.

This module is intentionally deterministic and local. It does not identify people or
perform online reverse-image search. It extracts broad, explainable visual/context
signals that help an analyst decide where to focus OCR, map, and manual verification.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:  # Pillow is a core project dependency, but keep this module safe in test/import contexts.
    from PIL import Image, ImageStat
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageStat = None  # type: ignore


@dataclass(slots=True)
class CTFVisualClueProfile:
    available: bool = False
    scene_type: str = "visual analysis unavailable"
    confidence: int = 0
    visual_tags: list[str] = field(default_factory=list)
    clue_cards: list[dict[str, Any]] = field(default_factory=list)
    recommended_crops: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ratio(count: int, total: int) -> float:
    return count / max(1, total)


def _unique(values: list[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").split()).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def _crop_plan(width: int, height: int, *, map_like: bool, text_heavy: bool) -> list[dict[str, Any]]:
    """Return normalized crop boxes for CTF/manual OCR workflows."""
    plan = [
        {"name": "top_search_header", "box": [0.0, 0.0, 1.0, 0.22], "why": "map/search/header labels often hold place names or app context"},
        {"name": "center_map_canvas", "box": [0.14, 0.16, 0.88, 0.84], "why": "central map/image area usually contains road labels, landmarks, or visible signs"},
        {"name": "center_context_menu", "box": [0.30, 0.30, 0.70, 0.76], "why": "Google Maps right-click/context menus often expose exact coordinates at the top"},
        {"name": "lower_status_labels", "box": [0.0, 0.72, 1.0, 1.0], "why": "bottom UI bars often contain route duration, city labels, watermarks, or coordinates"},
    ]
    if width >= height * 1.35:
        plan.append({"name": "left_side_panel", "box": [0.0, 0.08, 0.36, 0.92], "why": "wide screenshots may include a route/search side panel"})
        plan.append({"name": "right_map_labels", "box": [0.52, 0.08, 1.0, 0.92], "why": "right-side map canvas may contain labels missed by global OCR"})
    if height >= width * 1.25:
        plan.append({"name": "upper_phone_app_bar", "box": [0.0, 0.0, 1.0, 0.16], "why": "phone screenshots often hide app/location context in the top app bar"})
        plan.append({"name": "middle_phone_map", "box": [0.06, 0.18, 0.94, 0.72], "why": "phone map area may need isolated OCR to read small labels"})
    if text_heavy and not map_like:
        plan.append({"name": "document_text_body", "box": [0.04, 0.12, 0.96, 0.92], "why": "text-heavy screenshot/document body crop"})
    return plan[:7]


def extract_ctf_visual_clues(path: Path | str) -> CTFVisualClueProfile:
    path = Path(path)
    if Image is None or not path.exists():
        return CTFVisualClueProfile(
            available=False,
            confidence=0,
            visual_tags=["visual analysis unavailable"],
            limitations=["Pillow is unavailable or evidence file does not exist."],
        )
    try:
        with Image.open(path) as img:
            width, height = img.size
            rgb = img.convert("RGB")
            sample = rgb.resize((120, 120))
            pixels = list(sample.getdata())
            stat = ImageStat.Stat(sample) if ImageStat is not None else None
    except Exception as exc:
        return CTFVisualClueProfile(
            available=False,
            confidence=0,
            visual_tags=["visual analysis unavailable"],
            limitations=[f"Image visual analysis failed: {exc.__class__.__name__}."],
        )

    total = max(1, len(pixels))
    light = _ratio(sum(1 for r, g, b in pixels if (r + g + b) / 3 >= 184), total)
    dark = _ratio(sum(1 for r, g, b in pixels if (r + g + b) / 3 <= 58), total)
    green = _ratio(sum(1 for r, g, b in pixels if g >= 116 and g >= r + 10 and g >= b - 12), total)
    blue_route = _ratio(sum(1 for r, g, b in pixels if b >= 140 and b >= r + 32 and g <= 165), total)
    orange_road = _ratio(sum(1 for r, g, b in pixels if r >= 175 and 82 <= g <= 170 and b <= 120), total)
    water_blue = _ratio(sum(1 for r, g, b in pixels if b >= 130 and g >= 105 and r <= 135), total)
    high_contrast = _ratio(sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) >= 58), total)
    aspect = width / max(1, height)
    texture = 0.0
    if stat is not None:
        try:
            texture = sum(stat.stddev) / max(1, len(stat.stddev))
        except Exception:
            texture = 0.0

    tags: list[str] = []
    cards: list[dict[str, Any]] = []
    score = 20

    def add(tag: str, conf: int, why: str, source: str = "local-pixel-heuristics") -> None:
        tags.append(tag)
        cards.append({
            "clue_type": "visual",
            "value": tag,
            "source": source,
            "confidence": max(0, min(100, conf)),
            "evidence_strength": "weak_signal" if conf < 65 else "lead",
            "why_it_matters": why,
        })

    map_like = False
    if light >= 0.38 and high_contrast >= 0.07:
        map_like = True
        score += 20
        add("light tiled map/UI canvas", 54, "A light, high-contrast canvas can indicate a map or UI screenshot; OCR/map labels are the next validation step.")
    if green >= 0.035:
        map_like = True
        score += 8
        add("green park/terrain regions", 48, "Green regions may be parks/terrain on a map or outdoor scene clues.")
    if blue_route >= 0.003:
        map_like = True
        score += 18
        add("blue route/path overlay", 62, "Blue/purple route overlays are useful map/navigation clues, but do not prove real device location alone.")
    if orange_road >= 0.004:
        map_like = True
        score += 8
        add("orange/yellow road-highlight pattern", 46, "Road-highlight colors can support map context and guide crop OCR.")
    if water_blue >= 0.08:
        score += 7
        add("large blue/water or map-region signal", 44, "Large blue regions can support coastline/river/map hypotheses when combined with labels.")
    if dark >= 0.38 and high_contrast >= 0.05:
        score += 10
        add("dark application screenshot", 42, "Dark UI screenshots often need high-contrast OCR preprocessing.")
    if texture >= 58 and not map_like:
        score += 8
        add("high-detail real-world texture", 42, "Texture suggests a real-world photo; use object/signage OCR and EXIF before location claims.")
    if texture < 22:
        add("low-detail flat/exported image", 35, "Low texture may indicate exported graphic/screenshot; rely on source/custody and OCR.")
    if aspect >= 1.45:
        add("wide desktop/export screenshot", 38, "Wide aspect ratio often contains side panels or headers that need separate crop OCR.")
    elif aspect <= 0.72:
        add("tall mobile screenshot", 38, "Tall mobile screenshots benefit from top-bar and center-panel crop OCR.")

    if map_like:
        scene = "map/navigation candidate"
    elif texture >= 58:
        scene = "real-world/photo candidate"
    elif dark >= 0.38 or light >= 0.50:
        scene = "application/screenshot candidate"
    else:
        scene = "general image candidate"

    text_heavy = high_contrast >= 0.18 and (light >= 0.45 or dark >= 0.35)
    limitations = [
        "Visual clue engine is deterministic and local; it narrows search direction but does not identify exact locations.",
        "Treat visual-only candidates as weak signals until OCR, GPS, map URL, or analyst verification corroborates them.",
    ]
    return CTFVisualClueProfile(
        available=True,
        scene_type=scene,
        confidence=max(0, min(100, score)),
        visual_tags=_unique(tags, limit=12),
        clue_cards=cards[:12],
        recommended_crops=_crop_plan(width, height, map_like=map_like, text_heavy=text_heavy),
        limitations=limitations,
    )
