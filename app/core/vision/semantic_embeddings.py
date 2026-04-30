from __future__ import annotations

"""Offline image semantic fingerprinting.

This is not a branded CLIP implementation; it is a dependency-free semantic
fingerprint that gives GeoTrace practical similarity/search features today.  If a
real local CLIP/SigLIP runner is configured through local_vision_model.py, its
outputs are fused separately.  The fingerprint is deterministic, privacy-safe,
and good enough for duplicate/near-duplicate triage, crop priority, and broad
scene buckets.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


@dataclass(slots=True)
class SemanticImageProfile:
    provider: str = "geotrace-semantic-fingerprint-v1"
    fingerprint: str = ""
    vector: list[float] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    similarity_notes: list[str] = field(default_factory=list)
    confidence: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hist(values: list[int], bins: int = 8) -> list[float]:
    counts = [0] * bins
    if not values:
        return [0.0] * bins
    for value in values:
        idx = min(bins - 1, max(0, int(value) * bins // 256))
        counts[idx] += 1
    total = max(1, len(values))
    return [round(c / total, 5) for c in counts]


def _edge_density(gray: list[int], width: int, height: int) -> float:
    if width < 2 or height < 2:
        return 0.0
    edges = 0
    total = 0
    for y in range(height - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(width - 1):
            v = gray[row + x]
            if abs(v - gray[row + x + 1]) >= 24 or abs(v - gray[next_row + x]) >= 24:
                edges += 1
            total += 1
    return edges / max(1, total)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    ln = math.sqrt(sum(a * a for a in left))
    rn = math.sqrt(sum(b * b for b in right))
    if not ln or not rn:
        return 0.0
    return max(-1.0, min(1.0, dot / (ln * rn)))


def compare_semantic_profiles(left: SemanticImageProfile, right: SemanticImageProfile) -> dict[str, Any]:
    score = round((_cosine(left.vector, right.vector) + 1) * 50, 2)
    label = "low_similarity"
    if score >= 96:
        label = "near_duplicate"
    elif score >= 90:
        label = "strong_visual_family"
    elif score >= 82:
        label = "possible_visual_family"
    shared = sorted(set(left.tags) & set(right.tags))[:8]
    return {"score": score, "label": label, "shared_tags": shared}


def build_semantic_image_profile(file_path: Path | str) -> SemanticImageProfile:
    profile = SemanticImageProfile()
    try:
        with Image.open(file_path) as img:
            img.load()
            original_size = img.size
            work = img.convert("RGB")
            work.thumbnail((128, 128))
            gray_img = work.convert("L")
            pixels = list(work.getdata())
            gray = list(gray_img.getdata())
            stat = ImageStat.Stat(work)
    except Exception as exc:
        profile.warnings.append(f"Semantic fingerprint failed: {exc}")
        return profile

    if not pixels:
        profile.warnings.append("No pixels available for semantic fingerprint.")
        return profile

    r = [p[0] for p in pixels]
    g = [p[1] for p in pixels]
    b = [p[2] for p in pixels]
    avg = [int((rr + gg + bb) / 3) for rr, gg, bb in pixels]
    spread = [max(p) - min(p) for p in pixels]
    edge = _edge_density(gray, work.width, work.height)
    brightness = sum(avg) / max(1, len(avg))
    colorfulness = sum(spread) / max(1, len(spread))
    contrast = sum(stat.stddev) / max(1, len(stat.stddev))
    white_ratio = sum(1 for x in avg if x >= 232) / max(1, len(avg))
    dark_ratio = sum(1 for x in avg if x <= 35) / max(1, len(avg))
    green_ratio = sum(1 for rr, gg, bb in pixels if gg >= rr + 10 and gg >= bb - 8 and gg >= 95) / max(1, len(pixels))
    blue_ratio = sum(1 for rr, gg, bb in pixels if bb >= rr + 20 and bb >= gg and bb >= 95) / max(1, len(pixels))
    red_ratio = sum(1 for rr, gg, bb in pixels if rr >= gg + 25 and rr >= bb + 25 and rr >= 120) / max(1, len(pixels))
    neutral_ratio = sum(1 for p in pixels if max(p) - min(p) <= 22 and 60 <= sum(p) / 3 <= 220) / max(1, len(pixels))

    vector = []
    vector.extend(_hist(r))
    vector.extend(_hist(g))
    vector.extend(_hist(b))
    vector.extend(_hist(avg))
    vector.extend([round(edge, 5), round(brightness / 255, 5), round(colorfulness / 255, 5), round(contrast / 128, 5)])
    vector.extend([round(white_ratio, 5), round(dark_ratio, 5), round(green_ratio, 5), round(blue_ratio, 5), round(red_ratio, 5), round(neutral_ratio, 5)])

    raw = ",".join(f"{item:.5f}" for item in vector)
    profile.fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    profile.vector = vector

    tags: list[str] = []
    if edge >= 0.13 and (white_ratio >= 0.14 or dark_ratio >= 0.18):
        tags.append("ui_or_screenshot_like")
    if green_ratio >= 0.08:
        tags.append("outdoor_green_signal")
    if blue_ratio >= 0.08:
        tags.append("blue_sky_water_or_route_signal")
    if neutral_ratio >= 0.25 and edge >= 0.07:
        tags.append("road_document_or_map_neutral_signal")
    if red_ratio >= 0.018:
        tags.append("red_marker_or_warning_signal")
    if colorfulness >= 62:
        tags.append("high_colorfulness")
    if contrast <= 14 and edge <= 0.025:
        tags.append("low_information_flat_image")
    if brightness <= 35:
        tags.append("very_dark")
    elif brightness >= 225:
        tags.append("very_bright")

    profile.tags = tags[:12]
    profile.confidence = max(35, min(88, int(45 + min(edge * 120, 22) + min(contrast / 5, 15) + min(len(tags) * 3, 12))))
    profile.similarity_notes = [
        "Fingerprint supports local duplicate/near-duplicate triage without uploading evidence.",
        "Use a real CLIP/SigLIP runner for semantic landmark identity; this vector is a deterministic fallback.",
    ]
    profile.metrics = {
        "original_dimensions": f"{original_size[0]}x{original_size[1]}",
        "thumbnail_dimensions": f"{work.width}x{work.height}",
        "edge_density": round(edge, 5),
        "brightness_mean": round(brightness, 2),
        "contrast_stddev": round(contrast, 2),
        "colorfulness_proxy": round(colorfulness, 2),
        "white_ratio": round(white_ratio, 4),
        "dark_ratio": round(dark_ratio, 4),
        "green_ratio": round(green_ratio, 4),
        "blue_ratio": round(blue_ratio, 4),
        "red_ratio": round(red_ratio, 4),
        "neutral_ratio": round(neutral_ratio, 4),
        "vector_dimensions": len(vector),
    }
    return profile
