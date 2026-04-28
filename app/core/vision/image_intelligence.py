from __future__ import annotations

"""Offline image-detail intelligence for OSINT/CTF triage.

The module stays deterministic, privacy-safe, and fast. It does not call online
recognition services and does not claim exact object identity. Instead it turns
image pixels into explainable analyst signals: layout type, quality limits,
map/UI/photo likelihood, tile-level attention regions, crop priorities, and
methodology steps that can be shown in the UI/report.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
import math
import re

from PIL import Image, ImageStat


@dataclass(slots=True)
class ImageDetailProfile:
    label: str = "Image detail profile unavailable"
    confidence: int = 0
    summary: str = "Image-detail analysis has not run yet."
    cues: list[str] = field(default_factory=list)
    layout_hints: list[str] = field(default_factory=list)
    object_hints: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    attention_regions: list[dict[str, Any]] = field(default_factory=list)
    scene_descriptors: list[str] = field(default_factory=list)
    methodology_steps: list[str] = field(default_factory=list)
    performance_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "summary": self.summary,
            "cues": list(self.cues),
            "layout_hints": list(self.layout_hints),
            "object_hints": list(self.object_hints),
            "quality_flags": list(self.quality_flags),
            "metrics": dict(self.metrics),
            "limitations": list(self.limitations),
            "next_actions": list(self.next_actions),
            "attention_regions": list(self.attention_regions),
            "scene_descriptors": list(self.scene_descriptors),
            "methodology_steps": list(self.methodology_steps),
            "performance_notes": list(self.performance_notes),
        }


def _unique(items: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" -:|•·")
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


def _edge_density(gray: list[int], width: int, height: int) -> float:
    if width < 2 or height < 2 or not gray:
        return 0.0
    edges = 0
    total = 0
    for y in range(height - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(width - 1):
            value = gray[row + x]
            if abs(value - gray[row + x + 1]) >= 28 or abs(value - gray[next_row + x]) >= 28:
                edges += 1
            total += 1
    return edges / max(1, total)


def _block_variance(gray: list[int], width: int, height: int, block: int = 12) -> float:
    if width < block or height < block:
        return 0.0
    variances: list[float] = []
    for y in range(0, height - block + 1, block):
        for x in range(0, width - block + 1, block):
            values = [gray[(y + yy) * width + (x + xx)] for yy in range(block) for xx in range(block)]
            mean = sum(values) / len(values)
            variances.append(sum((item - mean) ** 2 for item in values) / len(values))
    return sum(variances) / max(1, len(variances))


def _ratios(pixels: list[tuple[int, int, int]], alpha: list[int] | None = None) -> dict[str, float]:
    total = max(1, len(pixels))
    light = dark = saturated = green = sky = water = red_alert = yellow = skinish = white_ui = black_ui = 0
    blue_route = gray_road = orange_marker = purple_ui = 0
    for red, green_ch, blue in pixels:
        avg = (red + green_ch + blue) / 3
        spread = max(red, green_ch, blue) - min(red, green_ch, blue)
        if avg >= 190:
            light += 1
        if avg <= 45:
            dark += 1
        if spread >= 60:
            saturated += 1
        if green_ch >= 105 and green_ch >= red + 8 and green_ch >= blue - 10:
            green += 1
        if blue >= 145 and green_ch >= 110 and red <= 155 and blue >= red + 20:
            sky += 1
        if blue >= 95 and green_ch >= 70 and red <= 105 and blue >= red + 25:
            water += 1
        if red >= 155 and red >= green_ch + 35 and red >= blue + 35:
            red_alert += 1
        if red >= 170 and green_ch >= 145 and blue <= 100:
            yellow += 1
        if red >= 210 and 85 <= green_ch <= 175 and blue <= 90:
            orange_marker += 1
        if blue >= 155 and red <= 95 and 85 <= green_ch <= 190:
            blue_route += 1
        if 82 <= avg <= 205 and spread <= 22:
            gray_road += 1
        if red >= 120 and blue >= 145 and green_ch <= 120 and abs(red - blue) <= 90:
            purple_ui += 1
        if red > 95 and green_ch > 55 and blue > 35 and red > green_ch > blue and (red - blue) >= 35:
            skinish += 1
        if avg >= 232 and spread <= 24:
            white_ui += 1
        if avg <= 28 and spread <= 24:
            black_ui += 1
    alpha_ratio = 0.0
    if alpha:
        alpha_ratio = sum(1 for item in alpha if item < 255) / max(1, len(alpha))
    return {
        "light_ratio": round(light / total, 4),
        "dark_ratio": round(dark / total, 4),
        "saturated_ratio": round(saturated / total, 4),
        "vegetation_green_ratio": round(green / total, 4),
        "sky_blue_ratio": round(sky / total, 4),
        "water_blue_ratio": round(water / total, 4),
        "red_alert_ratio": round(red_alert / total, 4),
        "yellow_marker_ratio": round(yellow / total, 4),
        "orange_marker_ratio": round(orange_marker / total, 4),
        "blue_route_ratio": round(blue_route / total, 4),
        "gray_road_like_ratio": round(gray_road / total, 4),
        "purple_ui_ratio": round(purple_ui / total, 4),
        "skin_tone_like_ratio": round(skinish / total, 4),
        "white_ui_ratio": round(white_ui / total, 4),
        "black_ui_ratio": round(black_ui / total, 4),
        "transparent_or_alpha_ratio": round(alpha_ratio, 4),
    }


def _dominant_color_family(pixels: list[tuple[int, int, int]]) -> str:
    if not pixels:
        return "unknown"
    totals = {"dark": 0, "light": 0, "green": 0, "blue": 0, "red_or_orange": 0, "neutral_gray": 0, "mixed": 0}
    for red, green, blue in pixels:
        avg = (red + green + blue) / 3
        spread = max(red, green, blue) - min(red, green, blue)
        if avg <= 55:
            totals["dark"] += 1
        elif avg >= 205 and spread <= 35:
            totals["light"] += 1
        elif spread <= 20:
            totals["neutral_gray"] += 1
        elif green >= red + 12 and green >= blue - 8:
            totals["green"] += 1
        elif blue >= red + 20 and blue >= green:
            totals["blue"] += 1
        elif red >= green + 25 and red >= blue + 25:
            totals["red_or_orange"] += 1
        else:
            totals["mixed"] += 1
    return max(totals, key=totals.get)


def _tile_profiles(work: Image.Image, original_width: int, original_height: int, grid: int = 4) -> list[dict[str, Any]]:
    width, height = work.size
    if width < grid or height < grid:
        return []
    tiles: list[dict[str, Any]] = []
    tile_w = max(1, width // grid)
    tile_h = max(1, height // grid)
    for gy in range(grid):
        for gx in range(grid):
            left = gx * tile_w
            upper = gy * tile_h
            right = width if gx == grid - 1 else min(width, left + tile_w)
            lower = height if gy == grid - 1 else min(height, upper + tile_h)
            crop = work.crop((left, upper, right, lower)).convert("RGB")
            gray_img = crop.convert("L")
            pixels = list(crop.getdata())
            gray = list(gray_img.getdata())
            ratios = _ratios(pixels)
            stat = ImageStat.Stat(crop)
            brightness = sum(sum(pixel) / 3 for pixel in pixels) / max(1, len(pixels))
            contrast = sum(stat.stddev) / max(1, len(stat.stddev))
            edge = _edge_density(gray, crop.width, crop.height)
            colorfulness = sum(max(pixel) - min(pixel) for pixel in pixels) / max(1, len(pixels))
            # Text/UI saliency favors edges + contrast, while map saliency favors route/marker/green/road cues.
            text_score = edge * 100 + min(30.0, contrast / 2.5)
            map_score = (
                ratios["blue_route_ratio"] * 180
                + ratios["yellow_marker_ratio"] * 85
                + ratios["orange_marker_ratio"] * 90
                + ratios["vegetation_green_ratio"] * 38
                + ratios["gray_road_like_ratio"] * 20
            )
            attention = text_score + map_score + min(20.0, colorfulness / 5)
            region_x1 = round(left / max(1, width), 3)
            region_y1 = round(upper / max(1, height), 3)
            region_x2 = round(right / max(1, width), 3)
            region_y2 = round(lower / max(1, height), 3)
            original_box = [
                int(region_x1 * original_width),
                int(region_y1 * original_height),
                int(region_x2 * original_width),
                int(region_y2 * original_height),
            ]
            reasons: list[str] = []
            if edge >= 0.14:
                reasons.append("dense edge/text candidate")
            if ratios["blue_route_ratio"] >= 0.01:
                reasons.append("blue route/control-like pixels")
            if ratios["yellow_marker_ratio"] + ratios["orange_marker_ratio"] >= 0.015:
                reasons.append("marker/signage color pixels")
            if ratios["vegetation_green_ratio"] >= 0.08:
                reasons.append("green/outdoor/map land cue")
            if contrast >= 42:
                reasons.append("high local contrast")
            if colorfulness >= 52:
                reasons.append("high local color variety")
            if not reasons:
                reasons.append("baseline context tile")
            tiles.append(
                {
                    "region": f"R{gy + 1}C{gx + 1}",
                    "relative_box": [region_x1, region_y1, region_x2, region_y2],
                    "original_box": original_box,
                    "attention_score": round(attention, 2),
                    "edge_density": round(edge, 4),
                    "contrast_stddev": round(contrast, 2),
                    "brightness_mean": round(brightness, 2),
                    "dominant_color_family": _dominant_color_family(pixels),
                    "reasons": _unique(reasons, limit=4),
                }
            )
    tiles.sort(key=lambda item: (-float(item["attention_score"]), str(item["region"])))
    # Keep only meaningful crop priorities; include at least one tile for traceability.
    important = [tile for tile in tiles if float(tile["attention_score"]) >= 30 or tile["reasons"] != ["baseline context tile"]]
    return (important or tiles)[:6]


def _scene_descriptors(label: str, ratios: dict[str, float], edge: float, block_var: float, brightness: float, contrast: float) -> list[str]:
    descriptors: list[str] = []
    if "Map" in label or ratios["blue_route_ratio"] >= 0.004 or (ratios["white_ui_ratio"] >= 0.16 and ratios["gray_road_like_ratio"] >= 0.18):
        descriptors.append("map/navigation candidate: prioritize labels, route lines, pins, and share URLs")
    if ratios["vegetation_green_ratio"] >= 0.08 or ratios["sky_blue_ratio"] >= 0.08:
        descriptors.append("outdoor-context candidate: verify skyline, signage, roads, terrain, and shadows manually")
    if edge >= 0.18 and block_var >= 600:
        descriptors.append("dense-detail surface: crop high-edge regions before OCR to recover small labels")
    if ratios["white_ui_ratio"] >= 0.18 or ratios["black_ui_ratio"] >= 0.18:
        descriptors.append("UI/screenshot candidate: preserve source application/browser context")
    if ratios["red_alert_ratio"] >= 0.018 or ratios["yellow_marker_ratio"] >= 0.018 or ratios["orange_marker_ratio"] >= 0.014:
        descriptors.append("marker/signage-color cue: inspect pins, warning labels, road signs, or highlighted UI elements")
    if brightness <= 35:
        descriptors.append("dark-image limitation: enhance preview or crop before text/visual review")
    if contrast <= 14 and edge <= 0.025:
        descriptors.append("low-information surface: lean on metadata, hidden-content scan, and source context")
    return _unique(descriptors, limit=8)


def _clamp_int(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def _image_review_strategy(
    label: str,
    ratios: dict[str, float],
    edge: float,
    block_var: float,
    brightness: float,
    contrast: float,
    colorfulness: float,
    megapixels: float,
    attention_regions: list[dict[str, Any]],
    has_alpha: bool,
    fmt: str,
) -> dict[str, Any]:
    """Turn visual metrics into an analyst-safe review strategy.

    This is the v12.10.4 reasoning layer: it does not claim exact object
    recognition. It decides the most reliable workflow for the evidence item
    and exposes the decision as bounded, explainable scores.
    """
    top_attention = float(attention_regions[0].get("attention_score", 0) if attention_regions and isinstance(attention_regions[0], dict) else 0)
    ui_surface = 1.0 if (ratios["white_ui_ratio"] >= 0.16 or ratios["black_ui_ratio"] >= 0.16) else 0.0
    map_surface = 1.0 if ("Map" in label or ratios["blue_route_ratio"] >= 0.004 or ratios["gray_road_like_ratio"] >= 0.20) else 0.0
    outdoor_surface = 1.0 if (ratios["vegetation_green_ratio"] >= 0.07 or ratios["sky_blue_ratio"] >= 0.06 or ratios["water_blue_ratio"] >= 0.08) else 0.0

    ocr_priority = _clamp_int(
        edge * 180
        + contrast * 0.55
        + top_attention * 0.18
        + ui_surface * 18
        + ratios["red_alert_ratio"] * 180
        + ratios["yellow_marker_ratio"] * 130
    )
    map_priority = _clamp_int(
        map_surface * 38
        + ratios["blue_route_ratio"] * 650
        + ratios["orange_marker_ratio"] * 260
        + ratios["yellow_marker_ratio"] * 180
        + ratios["gray_road_like_ratio"] * 75
        + ratios["vegetation_green_ratio"] * 55
    )
    hidden_content_priority = _clamp_int(
        (28 if has_alpha else 0)
        + (18 if fmt.upper() in {"PNG", "WEBP", "BMP", "TIFF"} else 7)
        + (22 if edge <= 0.035 and contrast <= 20 else 0)
        + ratios["transparent_or_alpha_ratio"] * 450
        + min(18.0, megapixels * 1.8)
    )
    geolocation_potential = _clamp_int(
        map_priority * 0.55
        + outdoor_surface * 25
        + (15 if ratios["sky_blue_ratio"] >= 0.08 and ratios["vegetation_green_ratio"] >= 0.06 else 0)
        + (10 if ratios["red_alert_ratio"] >= 0.018 or ratios["orange_marker_ratio"] >= 0.014 else 0)
        + (8 if top_attention >= 45 else 0)
    )
    detail_complexity = _clamp_int(
        edge * 150
        + min(30.0, block_var / 90)
        + min(22.0, colorfulness / 4)
        + min(18.0, contrast / 4)
    )

    if map_priority >= 65:
        strategy = "map-first review"
        primary_focus = "Identify labels, route intent, pins, search/destination fields, and whether the map is displayed-place or device-location evidence."
    elif ocr_priority >= 67:
        strategy = "OCR-first crop review"
        primary_focus = "Crop high-attention regions before global OCR; preserve small labels, usernames, timestamps, and UI captions separately."
    elif geolocation_potential >= 62:
        strategy = "geolocation-hypothesis review"
        primary_focus = "Build place hypotheses from signage/terrain/skyline/layout cues, then demand independent corroboration."
    elif hidden_content_priority >= 62:
        strategy = "hidden-content-first review"
        primary_focus = "Inspect alpha/low-bit/channel artifacts before making content claims from visible pixels only."
    elif detail_complexity <= 35:
        strategy = "metadata/context-first review"
        primary_focus = "Visible pixels are weak; prioritize EXIF/source path/filename/custody/OCR diagnostics before visual conclusions."
    else:
        strategy = "balanced visual review"
        primary_focus = "Combine metadata, OCR crops, visual cues, and pixel-hidden checks without over-weighting any single weak signal."

    quality_gate = "ready_for_triage"
    safeguards: list[str] = []
    if brightness <= 35 or contrast <= 12:
        quality_gate = "needs_enhancement_before_claims"
        safeguards.append("Enhance or crop low-contrast regions before relying on OCR/object hints.")
    if map_priority >= 55:
        safeguards.append("Never treat a displayed map as device GPS unless native GPS, history, or app context corroborates it.")
    if hidden_content_priority >= 55:
        safeguards.append("Keep hidden-content output separate from visible OCR to avoid mixing evidence families.")
    if geolocation_potential >= 60:
        safeguards.append("Require at least two independent non-visual anchors before final location wording.")
    if not safeguards:
        safeguards.append("Keep all visual labels as leads until validated by OCR, metadata, or analyst review.")

    if geolocation_potential >= 60:
        corroboration_target = "3-source location packet: native metadata/source URL + OCR/signage + manual map/landmark validation"
    elif ocr_priority >= 65:
        corroboration_target = "2-pass OCR packet: full image OCR + region crop OCR/manual transcription"
    elif hidden_content_priority >= 60:
        corroboration_target = "hidden-content packet: alpha/LSB/channel notes + original hash + decoded artifacts"
    else:
        corroboration_target = "baseline packet: hash, source profile, visible cues, and analyst limitations"

    return {
        "analysis_strategy": strategy,
        "primary_focus": primary_focus,
        "quality_gate": quality_gate,
        "ocr_priority_score": ocr_priority,
        "map_review_priority_score": map_priority,
        "hidden_content_priority_score": hidden_content_priority,
        "geolocation_potential_score": geolocation_potential,
        "detail_complexity_score": detail_complexity,
        "corroboration_target": corroboration_target,
        "safeguards": _unique(safeguards, limit=5),
    }


def _methodology_steps(label: str, attention_regions: list[dict[str, Any]], has_alpha: bool, fmt: str, review_strategy: dict[str, Any] | None = None) -> list[str]:
    steps = [
        "1. Preserve the original + staged copy hashes before interpretation.",
        "2. Classify the visual surface first: screenshot/UI, map/navigation, outdoor photo, document, or low-information artifact.",
        "3. Use high-attention regions as crop priorities for OCR/manual zoom instead of scanning the whole image blindly.",
        "4. Separate facts from leads: GPS/coordinates/source URLs are anchors; color/object/layout hints are only investigative leads.",
        "5. Corroborate every location/object claim with at least one independent source family before report wording.",
    ]
    if review_strategy:
        steps.append(
            "6. Strategy gate: "
            + str(review_strategy.get("analysis_strategy", "balanced visual review"))
            + " — "
            + str(review_strategy.get("primary_focus", "combine visual, OCR, metadata, and custody signals."))
        )
    if attention_regions:
        first = attention_regions[0]
        steps.append(f"7. First crop priority: {first.get('region')} box={first.get('original_box')} because {', '.join(first.get('reasons', [])[:3])}.")
    if has_alpha:
        steps.append("8. Alpha channel exists; inspect transparency residue and alpha-plane hidden-content findings.")
    if fmt.upper() in {"JPEG", "JPG"}:
        steps.append("9. JPEG container detected; review recompression/editing clues before relying on fine pixel artifacts.")
    if "Map" in label:
        steps.append("10. For map-like images, identify whether the place is device location, searched place, route destination, or merely a displayed map.")
    if review_strategy:
        steps.append("11. Corroboration target: " + str(review_strategy.get("corroboration_target", "baseline packet")) + ".")
    return steps[:11]


def analyze_image_details(file_path: Path) -> ImageDetailProfile:
    profile = ImageDetailProfile(
        limitations=[
            "Offline visual intelligence is heuristic, not object recognition or facial/person identification.",
            "Object hints describe broad pixel patterns and must be corroborated with OCR, metadata, or manual review.",
        ],
        next_actions=[
            "Use the image-detail cues to prioritize OCR crops, map review, and hidden-content triage.",
            "Do not report heuristic object hints as facts unless a human analyst verifies them.",
        ],
        performance_notes=[
            "Runs offline using bounded thumbnails and a 4x4 tile grid; no network calls or heavyweight model inference.",
            "Designed to keep imports/rescans responsive while still producing explainable crop priorities.",
        ],
    )
    try:
        with Image.open(file_path) as image:
            image.load()
            original_width, original_height = image.size
            mode = image.mode
            fmt = image.format or file_path.suffix.upper().lstrip(".") or "Unknown"
            has_alpha = "A" in image.getbands() or mode in {"LA", "RGBA", "PA"}
            work = image.convert("RGBA")
            work.thumbnail((224, 224))
            width, height = work.size
            rgba_pixels = list(work.getdata())
            rgb_pixels = [(r, g, b) for r, g, b, _a in rgba_pixels]
            alpha_values = [a for _r, _g, _b, a in rgba_pixels] if has_alpha else []
            gray_img = work.convert("L")
            gray = list(gray_img.getdata())
            stat = ImageStat.Stat(work.convert("RGB"))
            info = dict(getattr(image, "info", {}) or {})
            tile_profiles = _tile_profiles(work, original_width, original_height)
    except Exception as exc:
        profile.summary = f"Image-detail analysis could not run: {exc}"
        profile.quality_flags.append("image decoder unavailable for visual intelligence")
        return profile

    total = max(1, len(rgb_pixels))
    ratios = _ratios(rgb_pixels, alpha_values)
    edge = _edge_density(gray, width, height)
    block_var = _block_variance(gray, width, height)
    brightness = sum(sum(pixel) / 3 for pixel in rgb_pixels) / total
    colorfulness = sum(max(pixel) - min(pixel) for pixel in rgb_pixels) / total
    contrast = sum(stat.stddev) / max(1, len(stat.stddev))
    aspect = original_width / max(1, original_height)
    megapixels = (original_width * original_height) / 1_000_000
    entropy_proxy = min(8.0, math.log2(max(1.0, 1 + block_var)) if block_var > 0 else 0.0)

    cues: list[str] = [
        f"dimensions {original_width}x{original_height}",
        f"format {fmt}/{mode}",
        f"dominant color family {_dominant_color_family(rgb_pixels)}",
    ]
    layout_hints: list[str] = []
    object_hints: list[str] = []
    quality_flags: list[str] = []
    confidence = 40
    label = "General image artifact"

    if aspect >= 1.55 or aspect <= 0.65:
        layout_hints.append("wide/tall screenshot-style aspect ratio")
        confidence += 5
    if ratios["white_ui_ratio"] >= 0.18 and edge >= 0.13:
        layout_hints.append("bright UI/document/map layout")
        confidence += 10
    if ratios["black_ui_ratio"] >= 0.22 and edge >= 0.08:
        layout_hints.append("dark UI/application layout")
        confidence += 8
    if edge >= 0.20 and block_var >= 650:
        layout_hints.append("dense text/UI edges or detailed urban texture")
        confidence += 8
    elif edge <= 0.035 and contrast <= 20:
        quality_flags.append("low-detail/flat image; hidden or OCR signals may be weak")

    if ratios["vegetation_green_ratio"] >= 0.08:
        object_hints.append("outdoor/green-region visual cue")
        confidence += 4
    if ratios["sky_blue_ratio"] >= 0.08:
        object_hints.append("sky/open-air visual cue")
        confidence += 4
    if ratios["water_blue_ratio"] >= 0.10:
        object_hints.append("water/blue-region visual cue")
        confidence += 3
    if ratios["gray_road_like_ratio"] >= 0.22 and edge >= 0.08:
        object_hints.append("road/document-neutral surface cue")
        confidence += 2
    if ratios["blue_route_ratio"] >= 0.004:
        object_hints.append("blue route/control-line cue")
        confidence += 5
    if ratios["red_alert_ratio"] >= 0.018:
        object_hints.append("red marker/warning/signage cue")
    if ratios["yellow_marker_ratio"] >= 0.018 or ratios["orange_marker_ratio"] >= 0.014:
        object_hints.append("yellow/orange marker/signage/road-color cue")
    if ratios["purple_ui_ratio"] >= 0.018:
        object_hints.append("purple/blue UI accent cue")
    if ratios["skin_tone_like_ratio"] >= 0.10:
        object_hints.append("person/skin-tone-like pixel cue; treat as non-identifying and verify manually")
    if ratios["transparent_or_alpha_ratio"] >= 0.02:
        quality_flags.append("non-opaque pixels present; inspect alpha and transparent RGB residue")

    if edge >= 0.11 and (ratios["white_ui_ratio"] >= 0.12 or ratios["black_ui_ratio"] >= 0.16):
        label = "Screenshot/UI-rich image"
        confidence = max(confidence, 68)
    if ratios["vegetation_green_ratio"] >= 0.07 and ratios["sky_blue_ratio"] >= 0.04 and edge <= 0.22:
        label = "Outdoor/photo-like image"
        confidence = max(confidence, 64)
    if ratios["white_ui_ratio"] >= 0.20 and (
        ratios["vegetation_green_ratio"] >= 0.035
        or ratios["yellow_marker_ratio"] >= 0.012
        or ratios["blue_route_ratio"] >= 0.004
        or ratios["gray_road_like_ratio"] >= 0.20
    ):
        label = "Map/document-style visual artifact"
        confidence = max(confidence, 72)
    if ratios["blue_route_ratio"] >= 0.012 and edge >= 0.06:
        label = "Map/navigation-route visual artifact"
        confidence = max(confidence, 78)
    if contrast <= 12 and edge <= 0.02:
        label = "Flat/low-information image"
        confidence = max(35, min(confidence, 54))

    if brightness <= 35:
        quality_flags.append("very dark image; OCR/visual clues may need enhancement")
    elif brightness >= 225:
        quality_flags.append("very bright image; text/edge contrast should be checked")
    if original_width < 360 or original_height < 360:
        quality_flags.append("small image; location/object recognition confidence is limited")
    if megapixels >= 8:
        quality_flags.append("large image; use region crops for responsive review instead of full-canvas OCR only")
    if fmt.upper() in {"JPEG", "JPG"} and ("quality" in info or "progressive" in info):
        cues.append("JPEG encoder metadata present")
    if colorfulness >= 70:
        cues.append("high colorfulness")
    if contrast >= 58:
        cues.append("high visual texture/contrast")
    if tile_profiles:
        top = tile_profiles[0]
        cues.append(f"top attention region {top.get('region')} score {top.get('attention_score')}")
        profile.next_actions.append(
            f"Start manual crop/OCR at {top.get('region')} {top.get('original_box')} because {', '.join(top.get('reasons', [])[:3])}."
        )

    scene_descriptors = _scene_descriptors(label, ratios, edge, block_var, brightness, contrast)
    review_strategy = _image_review_strategy(
        label=label,
        ratios=ratios,
        edge=edge,
        block_var=block_var,
        brightness=brightness,
        contrast=contrast,
        colorfulness=colorfulness,
        megapixels=megapixels,
        attention_regions=tile_profiles,
        has_alpha=has_alpha,
        fmt=fmt,
    )
    profile.next_actions.append(
        "Strategy: "
        + str(review_strategy.get("analysis_strategy", "balanced visual review"))
        + " — "
        + str(review_strategy.get("primary_focus", "combine visual, OCR, metadata, and custody signals."))
    )
    profile.next_actions.append("Corroboration target: " + str(review_strategy.get("corroboration_target", "baseline packet")) + ".")
    for safeguard in list(review_strategy.get("safeguards", []) or [])[:2]:
        profile.limitations.append(str(safeguard))
    methodology_steps = _methodology_steps(label, tile_profiles, has_alpha, fmt, review_strategy)

    profile.label = label
    profile.confidence = max(0, min(100, int(confidence)))
    profile.cues = _unique(cues, limit=12)
    profile.layout_hints = _unique(layout_hints, limit=10)
    profile.object_hints = _unique(object_hints, limit=10)
    profile.quality_flags = _unique(quality_flags, limit=10)
    profile.attention_regions = tile_profiles
    profile.scene_descriptors = scene_descriptors
    profile.methodology_steps = methodology_steps
    profile.metrics = {
        "format": fmt,
        "mode": mode,
        "dimensions": f"{original_width}x{original_height}",
        "megapixels": round(megapixels, 3),
        "thumbnail_dimensions": f"{width}x{height}",
        "brightness_mean": round(brightness, 2),
        "contrast_stddev": round(contrast, 2),
        "colorfulness_proxy": round(colorfulness, 2),
        "edge_density": round(edge, 4),
        "block_variance": round(block_var, 2),
        "entropy_proxy": round(entropy_proxy, 3),
        "aspect_ratio": round(aspect, 4),
        "attention_region_count": len(tile_profiles),
        "dominant_color_family": _dominant_color_family(rgb_pixels),
        "analysis_strategy": review_strategy.get("analysis_strategy", "balanced visual review"),
        "analysis_primary_focus": review_strategy.get("primary_focus", ""),
        "quality_gate": review_strategy.get("quality_gate", "ready_for_triage"),
        "ocr_priority_score": review_strategy.get("ocr_priority_score", 0),
        "map_review_priority_score": review_strategy.get("map_review_priority_score", 0),
        "hidden_content_priority_score": review_strategy.get("hidden_content_priority_score", 0),
        "geolocation_potential_score": review_strategy.get("geolocation_potential_score", 0),
        "detail_complexity_score": review_strategy.get("detail_complexity_score", 0),
        "corroboration_target": review_strategy.get("corroboration_target", "baseline packet"),
        "strategy_safeguards": list(review_strategy.get("safeguards", []) or []),
        **ratios,
    }
    cue_text = "; ".join(
        _unique(
            [
                *profile.scene_descriptors,
                *profile.layout_hints,
                *profile.object_hints,
                *profile.quality_flags,
                *profile.cues,
            ],
            limit=5,
        )
    )
    profile.summary = (
        f"Image detail AI v5: {label} ({profile.confidence}% confidence). "
        f"Strategy: {review_strategy.get('analysis_strategy', 'balanced visual review')}. "
        f"Key visual cues: {cue_text or 'low-context image'}."
    )
    return profile
