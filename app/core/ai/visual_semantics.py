from __future__ import annotations

"""Deterministic visual-semantics helpers for the local AI analyst.

The goal is not object recognition.  This module converts broad pixel/layout
features into safe, explainable cues that help the AI Guardian decide whether an
artifact looks like a map screenshot, text-heavy UI, document/export, or natural
photo.  Every cue is intentionally phrased as a visual/layout signal, not a
factual claim about the real-world scene.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
import logging

from PIL import Image, ImageStat

LOGGER = logging.getLogger("geotrace.ai.visual_semantics")


@dataclass(slots=True)
class VisualSemanticProfile:
    label: str = "Unknown visual profile"
    confidence: int = 0
    cues: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def short_label(self) -> str:
        return f"{self.label} ({self.confidence}%)"


def _unique(items: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(str(item or "").split()).strip(" -:|•·")
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def analyze_visual_semantics(file_path: Path) -> VisualSemanticProfile:
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            sample = img.convert("RGB").resize((128, 128))
            pixels = list(sample.getdata())
            stat = ImageStat.Stat(sample)
    except Exception as exc:  # pragma: no cover - depends on external/corrupt images
        LOGGER.debug("Visual semantic analysis unavailable for %s: %s", file_path, exc)
        return VisualSemanticProfile(
            label="Visual analysis unavailable",
            confidence=0,
            cues=["visual analysis unavailable"],
            limitations=["The image could not be opened by the local visual-semantic analyzer."],
        )

    total = max(1, len(pixels))
    aspect = width / max(1, height)
    brightness_values = [(r + g + b) / 3 for r, g, b in pixels]
    brightness = sum(brightness_values) / total
    light_ratio = sum(1 for value in brightness_values if value >= 185) / total
    dark_ratio = sum(1 for value in brightness_values if value <= 55) / total
    edge_like = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) >= 45) / total
    saturation_like = sum(max(r, g, b) - min(r, g, b) for r, g, b in pixels) / total
    green_ratio = sum(1 for r, g, b in pixels if g >= 118 and g >= r + 10 and g >= b - 8) / total
    blue_line_ratio = sum(1 for r, g, b in pixels if b >= 145 and r <= 145 and g <= 135 and b >= r + 35) / total
    red_marker_ratio = sum(1 for r, g, b in pixels if r >= 180 and g <= 100 and b <= 110) / total
    white_panel_ratio = sum(1 for r, g, b in pixels if r >= 230 and g >= 230 and b >= 230) / total
    mean_std = sum(stat.stddev) / max(1, len(stat.stddev))

    scores: dict[str, int] = {
        "Map/navigation visual profile": 0,
        "Text-heavy UI/screenshot profile": 0,
        "Document/export visual profile": 0,
        "Natural-photo visual profile": 0,
        "Low-detail/blank visual profile": 0,
    }
    cues: list[str] = [f"dimensions {width}x{height}"]
    tags: list[str] = []

    if width >= 700 and height >= 450 and (aspect >= 1.35 or aspect <= 0.75):
        scores["Text-heavy UI/screenshot profile"] += 10
        cues.append("screenshot-like canvas shape")
        tags.append("screenshot-layout")
    if light_ratio >= 0.38 and edge_like >= 0.08:
        scores["Map/navigation visual profile"] += 20
        scores["Text-heavy UI/screenshot profile"] += 10
        cues.append("bright structured UI/map canvas")
    if green_ratio >= 0.035:
        scores["Map/navigation visual profile"] += 12
        scores["Natural-photo visual profile"] += 4
        cues.append("green region signal")
    if blue_line_ratio >= 0.003:
        scores["Map/navigation visual profile"] += 24
        cues.append("blue route/line signal")
        tags.append("route-like-visual-line")
    if red_marker_ratio >= 0.001:
        scores["Map/navigation visual profile"] += 7
        cues.append("red marker/POI-like visual signal")
    if white_panel_ratio >= 0.55 and edge_like <= 0.24:
        scores["Document/export visual profile"] += 20
        cues.append("large white document/export panel")
    if dark_ratio >= 0.38 and edge_like >= 0.06:
        scores["Text-heavy UI/screenshot profile"] += 18
        cues.append("dark application screenshot pattern")
    if saturation_like >= 45 and 65 <= brightness <= 190 and mean_std >= 42:
        scores["Natural-photo visual profile"] += 18
        cues.append("natural-photo texture/color distribution")
    if mean_std < 18 or (white_panel_ratio >= 0.78 and edge_like <= 0.12):
        scores["Low-detail/blank visual profile"] += 22
        cues.append("low-detail or mostly blank image")
    if mean_std > 58:
        tags.append("high-detail-texture")
    if light_ratio >= 0.45:
        tags.append("bright-canvas")
    if dark_ratio >= 0.38:
        tags.append("dark-canvas")

    label, raw_score = max(scores.items(), key=lambda item: item[1])
    if raw_score <= 0:
        label = "General visual profile"
        raw_score = 25
    confidence = max(0, min(92, 34 + raw_score))

    limitations = [
        "Visual semantics are broad layout/color cues, not object recognition.",
        "Use OCR, metadata, source context, and manual review before making factual claims.",
    ]
    if label == "Map/navigation visual profile":
        limitations.append("A map-looking screenshot can show a searched/displayed place without proving device presence.")
    if label == "Low-detail/blank visual profile":
        limitations.append("Low-detail images require external context; visual cues alone are weak.")

    return VisualSemanticProfile(
        label=label,
        confidence=confidence,
        cues=_unique(cues, limit=10),
        tags=_unique(tags, limit=8),
        limitations=_unique(limitations, limit=5),
    )
