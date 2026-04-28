"""Visible text, OCR, map-label, and source-profile extraction implementation.

Moved from app.core.visual_clues during v12.10.2 organization-only refactor.
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageFilter, ImageOps

from ..ocr_runtime import configure_pytesseract
from ..ocr_modes import OCRCacheKey, normalize_ocr_mode, read_ocr_cache, write_ocr_cache
from ..osint.map_url_parser import parse_map_url_signals
from ..osint.region_ocr import classify_ocr_regions

LOGGER = logging.getLogger("geotrace.visual_clues")

try:  # pragma: no cover - optional runtime dependency
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


MAP_COORD_PATTERNS = [
    re.compile(r"@\s*(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})(?:\s*,\s*(\d+(?:\.\d+)?)z)?", re.IGNORECASE),
    re.compile(r"(?:q|ll|center)=\s*(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})", re.IGNORECASE),
    re.compile(r"\b(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})\b"),
]

TIME_PATTERNS = [
    re.compile(r"\b(20\d{2})[-/:.](\d{2})[-/:.](\d{2})[ T](\d{1,2})[:.](\d{2})(?::(\d{2}))?\b"),
    re.compile(r"\b(\d{1,2}):(\d{2})\s*([AP]M)\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b"),
]

LOCATION_KEYWORDS = (
    # English venue/location indicators
    "street", "road", "hospital", "airport", "park", "mall", "city", "district", "bridge",
    "mosque", "church", "metro", "university", "school", "tower", "square", "station",
    "cairo", "giza", "heliopolis", "alexandria", "restaurant", "cafe", "venue", "hotel",
    "museum", "bank", "river", "nile", "corniche", "zamalek", "dokki", "tahrir", "nasr city",
    # Arabic venue/location indicators. Keep these as Unicode literals; OCR on Egypt/Arabic maps often
    # returns useful place names even when coordinates are absent.
    "مطار", "مستشفى", "مستشفي", "مدينة", "شارع", "طريق", "مول", "حديقة", "الزيتون", "المرج",
    "القاهرة", "الجيزة", "القاهره", "جيزة", "الزمالك", "الدقي", "التحرير", "قصر", "النيل",
    "كوبري", "كوبرى", "محطة", "محطه", "مترو", "ميدان", "مسجد", "كنيسة", "كنيسه", "جامعة",
    "جامعه", "مدرسة", "مدرسه", "فندق", "مطعم", "كافيه", "مقهى", "بنك", "متحف", "نادي",
    "نادى", "كورنيش", "وسط البلد", "مدينة نصر", "الهرم", "المهندسين", "المعادي", "الزمالك",
)

PLACE_SUFFIXES = (
    "tower", "mall", "airport", "station", "bridge", "park", "hospital", "metro", "square",
    "museum", "university", "school", "cafe", "restaurant", "mosque", "church", "district",
    "hotel", "corridor",
)

MAP_UI_KEYWORDS = (
    "google maps", "maps.google", "google.com/maps", "maps/@", "directions", "street view",
    "route overview", "nearby", "satellite", "خرائط", "خريطة", "خريطه", "المسار", "اتجاهات",
    "موقع", "أماكن", "اماكن", "جوجل ماب", "google maps",
)

APP_PATTERNS = [
    ("Google Maps", ["google maps", "maps/@", "google.com/maps", "maps.google", "street view", "directions", "satellite", "route overview", "nearby", "خرائط", "خريطة", "خريطه", "اتجاهات", "جوجل ماب"]),
    ("Google Earth", ["google earth", "earth.google"]),
    ("WhatsApp", ["whatsapp", "wa.me", "last seen", "typing", "online"]),
    ("Telegram", ["telegram", "t.me", "forwarded message", "joined telegram"]),
    ("Signal", ["signal", "signal.org"]),
    ("Discord", ["discord", "voice connected", "server", "dm"]),
    ("Facebook", ["facebook", "messenger", "facebook.com"]),
    ("Instagram", ["instagram", "stories", "reels"]),
    ("X / Twitter", ["twitter", "x.com", "post", "retweet"]),
    ("Chrome", ["chrome", "google.com", "www.", "search", "bookmark"]),
    ("Edge", ["microsoft edge", "edge"]),
    ("Firefox", ["firefox"]),
    ("Safari", ["safari"]),
]


def _dedupe(items: List[str], limit: int = 12) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        item = re.sub(r"\s+", " ", item).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _normalize_text(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2013", "-")
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception as exc:
        LOGGER.warning("Could not hash %s: %s", path, exc)
        return "unavailable"


def _contains_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f" or "\u08a0" <= ch <= "\u08ff" for ch in text or "")


def _has_map_ui_signal(text: str) -> bool:
    lower = (text or "").lower()
    return any(token in lower for token in MAP_UI_KEYWORDS)


def _is_probable_place_label(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -:|•·")
    if len(cleaned) < 4:
        return False
    letters = sum(ch.isalpha() for ch in cleaned)
    arabic = _contains_arabic(cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    # Reject OCR/date/id noise such as "001 2026", "IMG 001", or pure timestamp fragments.
    if letters == 0 and not arabic:
        return False
    if digits > letters * 2 and not arabic:
        return False
    lower = cleaned.lower()
    if lower in {"google maps", "google map", "maps", "map", "خرائط", "خريطة", "خريطه", "جوجل ماب"}:
        return False
    blocked = {"img", "image", "screenshot", "screen", "capture", "png", "jpg", "jpeg", "2026", "2025", "2024"}
    tokens = [token.strip(".,:;()[]{}") for token in lower.split()]
    if tokens and all(token in blocked or token.isdigit() for token in tokens):
        return False
    return True


def _filename_map_labels(file_path: Path) -> List[str]:
    stem = re.sub(r"[_-]+", " ", file_path.stem or "")
    stem = re.sub(r"\b(?:img|image|screenshot|screen|capture|copy|duplicate|edited|export)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d{4}(?:[-_]?\d{2}){2}\b", " ", stem)
    stem = re.sub(r"\b\d{6,}\b", " ", stem)
    parts = [part.strip() for part in re.split(r"\s+", stem) if part.strip()]
    labels: List[str] = []
    capture: List[str] = []
    for token in parts:
        lower = token.lower().strip(".,:;()[]{}")
        if lower in {"map", "maps", "location", "route", "directions", "geo", "google", "venue"}:
            continue
        if lower.isdigit():
            continue
        if len(token) <= 2 and not _contains_arabic(token):
            continue
        capture.append(token)
    candidate = " ".join(capture[:4])
    if candidate and _is_probable_place_label(candidate):
        labels.append(candidate)
    return _dedupe(labels, limit=4)


def _ocr_language_candidates() -> List[str | None]:
    configured = os.getenv("GEOTRACE_OCR_LANG", "eng+ara").strip()
    ordered: List[str | None] = []
    # Try the requested bilingual pack first, then safe fallbacks. Avoid long cascades over
    # unavailable languages on large map screenshots.
    for item in [configured, "eng", None]:
        if item == "":
            item = None
        if item not in ordered:
            ordered.append(item)
    return ordered


def _ocr_image_to_string(candidate, *, config: str, timeout: float) -> str:
    if pytesseract is None:
        return ""
    configure_pytesseract(pytesseract)
    last_error: Exception | None = None
    for lang in _ocr_language_candidates():
        try:
            if lang is None:
                return pytesseract.image_to_string(candidate, config=config, timeout=timeout)
            return pytesseract.image_to_string(candidate, lang=lang, config=config, timeout=timeout)
        except Exception as exc:  # fallback when a language pack is not installed. Do not cascade timeouts.
            last_error = exc
            if "timeout" in str(exc).lower():
                raise exc
            continue
    if last_error is not None:
        raise last_error
    return ""



def _ocr_preprocess_variants(work: Image.Image, *, mode: str) -> list[tuple[str, Image.Image]]:
    """Return OCR preprocessing variants.

    quick/deep keep a small set for speed. map_deep adds high-contrast and sharpened
    versions because map screenshots often contain small Arabic/English place labels.
    """
    variants: list[tuple[str, Image.Image]] = [("gray", work)]
    if mode in {"deep", "map_deep"}:
        variants.append(("sharp", work.filter(ImageFilter.SHARPEN)))
    if mode == "map_deep":
        try:
            threshold = work.point(lambda p: 255 if p > 172 else 0)
            variants.append(("threshold", threshold))
        except Exception as exc:
            LOGGER.debug("OCR preprocessing variant failed: %s", exc)
        try:
            high_contrast = ImageOps.autocontrast(work.filter(ImageFilter.SHARPEN))
            variants.append(("high_contrast", high_contrast))
        except Exception as exc:
            LOGGER.debug("OCR preprocessing variant failed: %s", exc)
    return variants[:4]


def _extract_urls(text: str) -> List[str]:
    urls = re.findall(r"https?://[^\s\"'<>]+", text, flags=re.IGNORECASE)
    compact = text.replace(" ", "")
    if not urls and ("google.com/maps" in compact.lower() or "maps/@" in compact.lower()):
        idx = compact.lower().find("google.com/maps")
        if idx >= 0:
            candidate = compact[max(0, idx - 8): idx + 260]
            candidate = re.sub(r"^[^h]*", "https://", candidate) if not candidate.startswith("http") else candidate
            urls = [candidate]
    return _dedupe(urls, limit=8)


def _extract_usernames(text: str) -> List[str]:
    return _dedupe(re.findall(r"(?<!\w)@[A-Za-z0-9_.]{3,32}", text), limit=10)


def _looks_like_readable_line(line: str) -> bool:
    line = re.sub(r"\s+", " ", line or "").strip()
    if len(line) < 3:
        return False
    letters = sum(ch.isalpha() for ch in line)
    digits = sum(ch.isdigit() for ch in line)
    spaces = sum(ch.isspace() for ch in line)
    # Keep Arabic/Unicode OCR. The old ASCII-printable ratio discarded useful Arabic map labels.
    if letters + digits + spaces < max(3, int(len(line) * 0.35)):
        return False
    if re.fullmatch(r"[\W_]+", line, flags=re.UNICODE):
        return False
    # Drop common one-character OCR noise while preserving real Arabic/English labels.
    if len(line) <= 4 and letters <= 1 and digits == 0:
        return False
    return True


def _extract_location_like_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line or "").strip()
        lower = cleaned.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS):
            out.append(cleaned)
            continue
        if re.search(r"\b(?:st\.?|street|rd\.?|road|ave\.?|avenue|blvd\.?|district|city|park|mall|bridge|tower|station|hotel|hospital|metro|square)\b", lower):
            out.append(cleaned)
            continue
        if _contains_arabic(cleaned) and re.search(r"(شارع|طريق|ميدان|كوبري|كوبرى|محطة|محطه|مستشفى|مستشفي|فندق|مطعم|كافيه|مول|جامعة|جامعه|مسجد|كنيسة|كنيسه|القاهرة|القاهره|الجيزة|الزمالك|الدقي|النيل|التحرير)", cleaned):
            out.append(cleaned)
    return _dedupe(out, limit=12)


def _extract_map_labels(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line or "").strip(" -:|•·")
        if not cleaned:
            continue
        lower = cleaned.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS) and _is_probable_place_label(cleaned):
            out.append(cleaned)
            continue
        if _has_map_ui_signal(cleaned) and _is_probable_place_label(cleaned):
            out.append(cleaned)
            continue
        words = cleaned.split()
        if len(words) >= 2 and any(words[-1].lower().strip(".,") == suffix for suffix in PLACE_SUFFIXES) and _is_probable_place_label(cleaned):
            out.append(cleaned)
            continue
        if _contains_arabic(cleaned) and len(cleaned) >= 4 and re.search(r"(القاهرة|القاهره|الجيزة|النيل|كوبري|كوبرى|ميدان|شارع|طريق|مستشفى|مستشفي|فندق|مطعم|كافيه|مول|مترو|مسجد|جامعة|جامعه|الزمالك|الدقي|التحرير)", cleaned):
            out.append(cleaned)
    return _dedupe(out, limit=12)


def _extract_entity_lines(lines: List[str], merged_text: str) -> Dict[str, List[str]]:
    urls: List[str] = []
    times: List[str] = []
    locations: List[str] = []
    usernames: List[str] = []
    for line in lines:
        urls.extend(_extract_urls(line))
        usernames.extend(_extract_usernames(line))
        for pattern in TIME_PATTERNS:
            for match in pattern.finditer(line):
                times.append(match.group(0))
        lower = line.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS) or (_contains_arabic(line) and any(keyword in line for keyword in LOCATION_KEYWORDS)):
            locations.append(line)
    app_names = []
    lower = merged_text.lower()
    for app, tokens in APP_PATTERNS:
        if any(token in lower for token in tokens):
            app_names.append(app)
    return {
        "urls": _dedupe(urls, limit=8),
        "times": _dedupe(times, limit=8),
        "locations": _dedupe(locations + _extract_location_like_lines(lines), limit=10),
        "usernames": _dedupe(usernames, limit=8),
        "app_names": _dedupe(app_names, limit=6),
        "map_labels": _extract_map_labels(lines),
    }


def _detect_app(text: str, app_names: List[str]) -> str:
    if app_names:
        return app_names[0]
    lower = text.lower()
    for app, tokens in APP_PATTERNS:
        if any(token in lower for token in tokens):
            return app
    return "Unknown"


def _detect_environment(file_name: str, width: int, height: int, text: str, source_type: str) -> str:
    lower = text.lower()
    if _has_map_ui_signal(text) or any(token in lower for token in ["http", "www.", ".com", "search google maps"]):
        return "Desktop Browser Capture" if width >= height else "Mobile Browser Capture"
    if any(token in lower for token in ["telegram", "whatsapp", "messenger", "discord", "instagram", "x.com", "twitter"]):
        return "Chat / Social Screenshot"
    if source_type in {"Screenshot", "Screenshot / Export", "Map Screenshot", "Browser Screenshot", "Chat Screenshot", "Desktop Capture"}:
        return "Desktop Screenshot" if width >= height else "Mobile Screenshot"
    if "camera" in source_type.lower() or source_type == "Camera Photo":
        return "Camera Capture"
    if "export" in source_type.lower():
        return "Exported Media"
    if "screenshot" in file_name.lower():
        return "Desktop Screenshot" if width >= height else "Mobile Screenshot"
    return "Unknown"


def _score_ocr(lines: List[str], zone_hits: List[str], entities: Dict[str, List[str]]) -> Tuple[int, str]:
    confidence = min(92, 28 + (len(lines) * 4) + (len(zone_hits) * 6))
    signal_count = sum(len(entities[key]) for key in ["urls", "times", "locations", "usernames", "app_names", "map_labels"])
    confidence = min(95, confidence + min(18, signal_count * 3))
    if signal_count >= 4:
        relevance = "High analyst relevance: OCR recovered multiple actionable entities that can support source, time, or location reasoning."
    elif signal_count >= 2:
        relevance = "Medium analyst relevance: OCR recovered a small set of useful entities that can assist triage and corroboration."
    elif lines:
        relevance = "Low-to-medium analyst relevance: OCR recovered readable context but only limited directly actionable entities."
    else:
        relevance = "Low analyst relevance: OCR returned weak or mostly structural text."
    return confidence, relevance


def extract_visible_text_clues(file_path: Path, width: int, height: int, *, source_hint: str = "", force: bool = False, mode: str | None = None, cache_dir: Path | None = None) -> Dict[str, object]:
    filename_map_labels = _filename_map_labels(file_path)
    filename_has_map_signal = _has_map_ui_signal(file_path.name)
    default = {
        "lines": [],
        "excerpt": "",
        "raw_text": "",
        "visible_urls": [],
        "visible_time_strings": [],
        "visible_location_strings": [],
        "app_detected": "Unknown",
        "app_names": [],
        "environment_profile": "Unknown",
        "ocr_note": "OCR not attempted.",
        "ocr_confidence": 0,
        "ocr_analyst_relevance": "OCR not attempted.",
        "ocr_username_entities": [],
        "ocr_map_labels": filename_map_labels,
        "ocr_language": os.getenv("GEOTRACE_OCR_LANG", "eng+ara"),
        "ocr_map_context": "Map/place context hinted by filename." if (filename_has_map_signal or filename_map_labels) else "No map/place context detected.",
    }
    mode = normalize_ocr_mode(mode)
    if mode == "off":
        default["ocr_note"] = "OCR skipped because GEOTRACE_OCR_MODE=off. Forced OCR cannot override an explicit off setting."
        return default
    cache_key_obj = None
    if cache_dir is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_key_obj = OCRCacheKey(
                file_sha256=_file_sha256(file_path),
                mode=mode,
                force=force,
                language=os.getenv("GEOTRACE_OCR_LANG", "eng+ara"),
            )
            cached = read_ocr_cache(cache_dir, cache_key_obj)
            if cached is not None:
                if (filename_has_map_signal or filename_map_labels) and not cached.get("ocr_map_labels"):
                    cached["ocr_map_labels"] = filename_map_labels
                if (filename_has_map_signal or filename_map_labels) and str(cached.get("ocr_map_context", "")).startswith("No map"):
                    cached["ocr_map_context"] = "Map/place context hinted by filename."
                cached["ocr_note"] = str(cached.get("ocr_note", "OCR loaded from cache.")) + " Cached result."
                return cached
        except Exception:
            cache_key_obj = None
    if pytesseract is None:
        default["ocr_note"] = "OCR engine is unavailable in this environment."
        return default
    if min(width, height) < 220 and not force:
        default["ocr_note"] = "OCR skipped because the image is too small for reliable on-screen clue extraction."
        return default
    if file_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        default["ocr_note"] = "OCR skipped because this format is not part of the screen-clue pipeline."
        return default

    zone_hits: List[str] = []
    text_blocks: List[str] = []
    region_text_blocks: Dict[str, List[str]] = {}
    try:
        with Image.open(file_path) as image:
            image.load()
            work = image.convert("L")
            work = ImageOps.autocontrast(work)
            if max(work.size) < 1700:
                work = work.resize((work.width * 2, work.height * 2))
            full_box = (0, 0, work.width, work.height)
            zone_specs: List[tuple[str, tuple[int, int, int, int], str]] = [("full", full_box, "--psm 11")]
            if force and mode not in {"deep", "map_deep"}:
                zone_specs.append(("top", (0, 0, work.width, max(180, int(work.height * 0.22))), "--psm 6"))
                zone_specs.append(("right", (int(work.width * 0.68), 0, work.width, work.height), "--psm 6"))
            if mode in {"deep", "map_deep"}:
                zone_specs.append(("top", (0, 0, work.width, max(180, int(work.height * 0.22))), "--psm 6"))
                zone_specs.append(("bottom", (0, int(work.height * 0.72), work.width, work.height), "--psm 6"))
                zone_specs.append(("left", (0, 0, max(240, int(work.width * 0.28)), work.height), "--psm 6"))
                zone_specs.append(("right", (int(work.width * 0.68), 0, work.width, work.height), "--psm 6"))
                zone_specs.append(("center", (int(work.width * 0.22), int(work.height * 0.18), int(work.width * 0.78), int(work.height * 0.82)), "--psm 11"))
            if mode == "map_deep":
                zone_specs.append(("map_search_bar", (0, 0, work.width, max(160, int(work.height * 0.16))), "--psm 6"))
                zone_specs.append(("map_bottom_sheet", (0, int(work.height * 0.62), work.width, work.height), "--psm 6"))

            variants = _ocr_preprocess_variants(work, mode=mode)
            for zone_name, box, config in zone_specs:
                for variant_name, variant_base in variants:
                    candidate = variant_base.crop(box) if box != full_box else variant_base
                    try:
                        timeout = float(os.getenv("GEOTRACE_OCR_TIMEOUT", "1.4"))
                        block = _ocr_image_to_string(candidate, config=config, timeout=timeout)
                    except Exception:
                        continue
                    if block and block.strip():
                        text_blocks.append(block)
                        region_text_blocks.setdefault(zone_name, []).append(block)
                        zone_hits.append(f"{zone_name}/{variant_name}")
    except Exception as exc:
        default["ocr_note"] = f"OCR failed: {exc.__class__.__name__}."
        return default

    merged = "\n".join(block for block in text_blocks if block).strip()
    if not merged:
        default["ocr_note"] = f"OCR attempted in mode={mode}, but no stable on-screen text was recovered."
        default["ocr_analyst_relevance"] = "OCR attempted but returned no stable analyst-readable text."
        return default

    raw_lines = [line for block in text_blocks for line in block.splitlines() if line.strip()]
    lines = _dedupe([line for line in raw_lines if _looks_like_readable_line(line)], limit=28)
    if not lines:
        default["ocr_note"] = f"OCR attempted in mode={mode}, but only low-value structural text was recovered."
        default["ocr_analyst_relevance"] = "OCR attempted but recovered only low-value structural/noisy text."
        default["raw_text"] = merged[:2500]
        return default
    excerpt = _normalize_text(" ".join(lines[:6]))[:280]
    entity_lines = _extract_entity_lines(lines, merged)
    confidence, relevance = _score_ocr(lines, zone_hits, entity_lines)
    merged_text = "\n".join(lines)
    app_detected = _detect_app(merged_text, entity_lines["app_names"])
    environment_profile = _detect_environment(file_path.name, width, height, merged_text, source_hint)
    zone_note = ", ".join(zone_hits[:4]) if zone_hits else "none"
    merged_map_labels = _dedupe(list(entity_lines["map_labels"]) + filename_map_labels, limit=10)
    map_context = "Map/place context detected." if (merged_map_labels or _has_map_ui_signal(merged_text) or filename_has_map_signal) else "No map/place context detected."
    region_signals = classify_ocr_regions({key: "\n".join(value) for key, value in region_text_blocks.items()})
    result = {
        "lines": lines[:28],
        "excerpt": excerpt,
        "raw_text": merged[:4000],
        "visible_urls": entity_lines["urls"],
        "visible_time_strings": entity_lines["times"],
        "visible_location_strings": entity_lines["locations"],
        "app_detected": app_detected,
        "app_names": entity_lines["app_names"],
        "ocr_username_entities": entity_lines["usernames"],
        "ocr_map_labels": merged_map_labels,
        "environment_profile": environment_profile,
        "ocr_note": f"OCR zones recovered from: {zone_note}. Mode={mode}. Lang={os.getenv('GEOTRACE_OCR_LANG', 'eng+ara')}",
        "ocr_language": os.getenv("GEOTRACE_OCR_LANG", "eng+ara"),
        "ocr_map_context": map_context,
        "ocr_confidence": confidence,
        "ocr_analyst_relevance": relevance,
        "ocr_region_signals": [signal.to_dict() for signal in region_signals],
    }
    if cache_dir is not None and cache_key_obj is not None:
        try:
            write_ocr_cache(cache_dir, cache_key_obj, result)
        except Exception as exc:
            LOGGER.debug("Could not write OCR cache for %s: %s", file_path, exc)
    return result


def parse_derived_geo(text_candidates: List[str], visible_urls: List[str], *, source_type: str = "Unknown") -> Dict[str, object]:
    haystacks = []
    haystacks.extend(visible_urls)
    haystacks.extend(text_candidates)
    joined = "\n".join(item for item in haystacks if item)
    if not joined:
        return {
            "latitude": None,
            "longitude": None,
            "display": "Unavailable",
            "source": "Unavailable",
            "confidence": 0,
            "note": "No screenshot-derived geolocation clue recovered.",
            "possible_geo_clues": [],
        }
    map_url_signals = parse_map_url_signals(haystacks, source="visible-text")
    coordinate_signal = next((signal for signal in map_url_signals if signal.coordinates is not None), None)
    if coordinate_signal is not None and coordinate_signal.coordinates is not None:
        lat, lon = coordinate_signal.coordinates
        display = f"{lat:.6f}, {lon:.6f}"
        confidence = min(88, coordinate_signal.confidence + (6 if source_type in {"Map Screenshot", "Browser Screenshot", "Screenshot", "Screenshot / Export"} else 0))
        note = (
            f"Derived geolocation clue parsed from {coordinate_signal.provider} visible map/coordinate text; "
            "corroborate it with browser history, saved links, or surrounding case context before courtroom use."
        )
        if coordinate_signal.zoom != "Unavailable":
            note += f" Zoom/context marker: {coordinate_signal.zoom}."
        return {
            "latitude": lat,
            "longitude": lon,
            "display": display,
            "source": coordinate_signal.provider,
            "confidence": confidence,
            "note": note,
            "possible_geo_clues": [display],
        }

    compact = joined.replace(" ", "")
    for pattern in MAP_COORD_PATTERNS:
        match = pattern.search(compact)
        if not match:
            continue
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
        except Exception:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        zoom = match.group(3) if match.lastindex and match.lastindex >= 3 else None
        display = f"{lat:.6f}, {lon:.6f}"
        source = "Visible Google Maps URL" if ("google" in joined.lower() or "maps" in joined.lower()) else "Visible coordinate text"
        confidence = 64 if "google" in joined.lower() else 52
        if source_type in {"Map Screenshot", "Browser Screenshot", "Screenshot", "Screenshot / Export"}:
            confidence += 6
        note = (
            "Derived geolocation clue parsed from on-screen map content or visible coordinate text; corroborate it with browser history, saved links, or surrounding case context before courtroom use."
        )
        if zoom:
            note = note[:-1] + f" Zoom/context marker: {zoom}z."
        return {
            "latitude": lat,
            "longitude": lon,
            "display": display,
            "source": source,
            "confidence": min(confidence, 78),
            "note": note,
            "possible_geo_clues": [display],
        }
    lower_joined = joined.lower()
    map_ui_detected = _has_map_ui_signal(joined) or source_type in {"Map Screenshot", "Browser Screenshot"}
    map_labels = _extract_map_labels([line for line in joined.splitlines() if line.strip()])
    location_hits = _extract_location_like_lines([line for line in joined.splitlines() if line.strip()])
    possible_geo_clues = _dedupe(map_labels + location_hits, limit=6)
    if possible_geo_clues:
        best = possible_geo_clues[0]
        confidence = 44 if map_ui_detected else 30
        return {
            "latitude": None,
            "longitude": None,
            "display": f"Possible geo clue: {best}",
            "source": "OCR map/place label",
            "confidence": confidence,
            "note": "Visible map/place labels suggest a possible location lead, but no stable coordinates were parsed. Preserve OCR text, map labels, browser history, and application context for manual venue reasoning.",
            "possible_geo_clues": possible_geo_clues,
        }
    if map_ui_detected:
        return {
            "latitude": None,
            "longitude": None,
            "display": "Map-like screenshot detected",
            "source": "Visual map UI",
            "confidence": 22,
            "note": "Map-style UI markers were detected, but no stable coordinates could be parsed. Preserve the screenshot, OCR text, and browser context for manual venue reasoning.",
            "possible_geo_clues": [],
        }
    return {
        "latitude": None,
        "longitude": None,
        "display": "Unavailable",
        "source": "Unavailable",
        "confidence": 0,
        "note": "No screenshot-derived geolocation clue recovered.",
        "possible_geo_clues": [],
    }


def infer_source_profile(
    file_path: Path,
    *,
    source_type: str,
    width: int,
    height: int,
    has_exif: bool,
    software: str,
    visible_urls: List[str],
    app_detected: str,
    visible_lines: List[str] | None = None,
    map_labels: List[str] | None = None,
) -> Dict[str, object]:
    reasons: List[str] = []
    name = file_path.name.lower()
    software_l = software.lower()
    joined = " ".join((visible_urls or []) + (visible_lines or []) + (map_labels or [])).lower()
    suffix = file_path.suffix.lower()
    if width <= 0 or height <= 0:
        reasons.append("The image parser could not recover stable dimensions, so the item is treated as a malformed/graphic asset rather than a screenshot.")
        return {"type": "Graphic Asset", "subtype": "Malformed Asset", "confidence": 74, "reasons": reasons}
    screenshot_like = source_type in {"Screenshot", "Screenshot / Export", "Messaging Export"} or "screenshot" in name or suffix in {".png", ".webp"}
    browser_like = bool(visible_urls) or "www." in joined or "http" in joined
    map_ui = app_detected in {"Google Maps", "Google Earth"} or any("google.com/maps" in url.lower() for url in visible_urls)
    chat_ui = app_detected in {"WhatsApp", "Telegram", "Signal", "Discord", "Facebook", "Instagram", "X / Twitter"}

    if map_ui or (map_labels and screenshot_like):
        reasons.extend([
            "Visible text suggests map-style UI or venue labels.",
            f"Detected application context: {app_detected}.",
        ])
        return {"type": "Screenshot", "subtype": "Map Screenshot", "confidence": 84 if map_ui else 74, "reasons": reasons}
    if app_detected in {"Chrome", "Safari", "Firefox", "Edge"} and browser_like:
        reasons.extend([
            "Browser-style text or URLs were recovered through OCR.",
            f"Application fingerprint suggests {app_detected}.",
        ])
        return {"type": "Screenshot", "subtype": "Browser Screenshot", "confidence": 78, "reasons": reasons}
    if chat_ui:
        reasons.extend([
            f"Application fingerprint suggests {app_detected}.",
            "Recovered on-screen text is consistent with chat/social UI.",
        ])
        return {"type": "Screenshot", "subtype": "Chat Screenshot", "confidence": 80, "reasons": reasons}
    if source_type == "Camera Photo":
        reasons.append("Native EXIF/container profile is consistent with camera-origin media.")
        if has_exif:
            reasons.append("Embedded EXIF strengthens original-capture posture.")
        return {"type": "Camera Photo", "subtype": "Camera Original", "confidence": 86 if has_exif else 62, "reasons": reasons}
    if source_type == "Edited / Exported":
        if any(term in software_l for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            reasons.append(f"Software tag '{software}' suggests an edit/export workflow.")
        else:
            reasons.append("Metadata profile points to export or editing history.")
        return {"type": "Edited / Exported", "subtype": "Edited Export", "confidence": 76, "reasons": reasons}
    if source_type in {"Screenshot", "Screenshot / Export"}:
        confidence = 72
        reasons.append("Source classification and file naming are consistent with a screenshot workflow.")
        if "screenshot" in name:
            confidence += 10
            reasons.append("Filename explicitly contains screenshot wording.")
        if width >= height:
            reasons.append("Landscape desktop-like aspect ratio reinforces desktop capture posture.")
            subtype = "Desktop Capture"
        else:
            reasons.append("Portrait/mobile-like aspect ratio suggests mobile screenshot posture.")
            subtype = "Mobile Screenshot"
        return {"type": "Screenshot", "subtype": subtype, "confidence": min(confidence, 88), "reasons": reasons}
    if source_type == "Messaging Export":
        reasons.append("Thin metadata plus messaging-like cues suggest an exported chat/media artifact.")
        return {"type": "Messaging Export", "subtype": "Chat Screenshot / Export", "confidence": 78, "reasons": reasons}
    if file_path.suffix.lower() in {".gif", ".bmp"}:
        reasons.append("Container/extension pair is more consistent with a graphic asset than a camera original.")
        return {"type": "Graphic Asset", "subtype": "Graphic Asset", "confidence": 70, "reasons": reasons}
    if not has_exif and file_path.suffix.lower() == ".png":
        reasons.append("PNG without EXIF is often screenshot/export media, though it may still be a generic graphic asset.")
        subtype = "Desktop Capture" if width >= height else "Mobile Screenshot"
        return {"type": "Screenshot / Export", "subtype": subtype, "confidence": 61, "reasons": reasons}
    if suffix in {".jpg", ".jpeg"} and not browser_like and not chat_ui and not map_ui and max(width, height) >= 1000:
        reasons.append("JPEG dimensions and lack of strong browser/chat cues look more like a photo asset than a UI capture.")
        if map_labels:
            reasons.append("Map-like words were seen, but they are not strong enough by themselves to override the broader photo posture.")
        return {"type": "Unknown", "subtype": "Photo-like Asset", "confidence": 58, "reasons": reasons}
    reasons.append("No decisive source fingerprint was recovered; keep provenance posture conservative.")
    return {"type": source_type or "Unknown", "subtype": source_type or "Unknown", "confidence": 48, "reasons": reasons}


def profile_source_details(
    file_path: Path,
    *,
    source_type: str,
    width: int,
    height: int,
    has_exif: bool,
    software: str,
    visible_urls: List[str],
    app_detected: str,
) -> Tuple[str, int]:
    profile = infer_source_profile(
        file_path,
        source_type=source_type,
        width=width,
        height=height,
        has_exif=has_exif,
        software=software,
        visible_urls=visible_urls,
        app_detected=app_detected,
    )
    return str(profile["subtype"]), int(profile["confidence"])
