from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps

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
    "street", "road", "hospital", "airport", "park", "mall", "city", "district", "bridge",
    "mosque", "church", "metro", "university", "school", "cairo", "giza", "heliopolis",
    "مطار", "مستشفى", "مدينة", "شارع", "طريق", "مول", "حديقة", "الزيتون", "المرج",
)

APP_PATTERNS = [
    ("Google Maps", ["google maps", "maps/@", "google.com/maps", "maps.google", "street view", "directions", "satellite"]),
    ("Google Earth", ["google earth", "earth.google"]),
    ("WhatsApp", ["whatsapp", "wa.me", "chat", "last seen"]),
    ("Telegram", ["telegram", "t.me", "channel", "forwarded message"]),
    ("Signal", ["signal", "signal.org"]),
    ("Discord", ["discord", "server", "voice connected"]),
    ("Facebook", ["facebook", "messenger", "facebook.com"]),
    ("Instagram", ["instagram", "stories", "reels"]),
    ("Chrome", ["chrome", "google.com", "www.", "search"]),
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


def _extract_urls(text: str) -> List[str]:
    normalized = text.replace(" ", "")
    urls = re.findall(r"https?://[^\s\"'<>]+", normalized, flags=re.IGNORECASE)
    if not urls and ("google.com/maps" in normalized.lower() or "maps/@" in normalized.lower()):
        start = normalized.lower().find("google.com/maps")
        if start >= 0:
            candidate = normalized[max(0, start - 8): start + 260]
            candidate = re.sub(r"^[^h]*", "https://", candidate) if not candidate.startswith("http") else candidate
            urls = [candidate]
    return _dedupe(urls, limit=8)


def _detect_app(text: str) -> str:
    lower = text.lower()
    for app, tokens in APP_PATTERNS:
        if any(token in lower for token in tokens):
            return app
    return "Unknown"


def _detect_environment(file_name: str, width: int, height: int, text: str, source_type: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ["google maps", "http", "www.", ".com", "search google maps", "directions", "street view"]):
        return "Desktop Browser Capture" if width >= height else "Mobile Browser Capture"
    if any(token in lower for token in ["telegram", "whatsapp", "messenger", "discord", "instagram"]):
        return "Chat / Social Screenshot"
    if source_type in {"Screenshot", "Screenshot / Export", "Map Screenshot", "Browser Screenshot"}:
        return "Desktop Screenshot" if width >= height else "Mobile Screenshot"
    if "camera" in source_type.lower() or source_type == "Camera Photo":
        return "Camera Capture"
    if "export" in source_type.lower():
        return "Exported Media"
    if "screenshot" in file_name.lower():
        return "Desktop Screenshot" if width >= height else "Mobile Screenshot"
    return "Unknown"


def _looks_like_readable_line(line: str) -> bool:
    line = re.sub(r"\s+", " ", line or "").strip()
    if len(line) < 3:
        return False
    letters = sum(ch.isalpha() for ch in line)
    digits = sum(ch.isdigit() for ch in line)
    spaces = sum(ch.isspace() for ch in line)
    printable = sum(32 <= ord(ch) <= 126 or ch.isspace() for ch in line)
    if printable / max(len(line), 1) < 0.92:
        return False
    if letters + digits + spaces < max(3, int(len(line) * 0.45)):
        return False
    if re.fullmatch(r"[\W_]+", line):
        return False
    return True


def _extract_location_like_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS):
            out.append(line)
            continue
        if re.search(r"(?:st\.?|street|rd\.?|road|ave\.?|avenue|blvd\.?|district|city|park|mall|bridge)", lower):
            out.append(line)
    return _dedupe(out, limit=10)


def _extract_entity_lines(lines: List[str]) -> Dict[str, List[str]]:
    urls: List[str] = []
    times: List[str] = []
    locations: List[str] = []
    for line in lines:
        urls.extend(_extract_urls(line))
        for pattern in TIME_PATTERNS:
            for match in pattern.finditer(line):
                times.append(match.group(0))
        lower = line.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS):
            locations.append(line)
    return {
        "urls": _dedupe(urls, limit=8),
        "times": _dedupe(times, limit=8),
        "locations": _dedupe(locations, limit=10),
    }


def extract_visible_text_clues(file_path: Path, width: int, height: int, *, source_hint: str = "", force: bool = False) -> Dict[str, object]:
    default = {
        "lines": [],
        "excerpt": "",
        "visible_urls": [],
        "visible_time_strings": [],
        "visible_location_strings": [],
        "app_detected": "Unknown",
        "environment_profile": "Unknown",
        "ocr_note": "OCR not attempted.",
    }
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
    try:
        with Image.open(file_path) as image:
            image.load()
            work = image.convert("L")
            work = ImageOps.autocontrast(work)
            if max(work.size) < 1700:
                scale = 2
                work = work.resize((work.width * scale, work.height * scale))
            zones = [
                ("full", work, "--psm 11"),
                ("top", work.crop((0, 0, work.width, max(180, int(work.height * 0.22)))), "--psm 6"),
                ("left", work.crop((0, 0, max(220, int(work.width * 0.35)), work.height)), "--psm 6"),
                ("bottom", work.crop((0, int(work.height * 0.72), work.width, work.height)), "--psm 6"),
            ]
            text_blocks = []
            for zone_name, candidate, config in zones:
                try:
                    block = pytesseract.image_to_string(candidate, config=config, timeout=5)
                except Exception:
                    continue
                if block and block.strip():
                    text_blocks.append(block)
                    zone_hits.append(zone_name)
    except Exception as exc:
        default["ocr_note"] = f"OCR failed: {exc.__class__.__name__}."
        return default

    merged = "\n".join(block for block in text_blocks if block).strip()
    if not merged:
        default["ocr_note"] = "OCR completed but no stable on-screen text was recovered."
        return default

    raw_lines = [line for block in text_blocks for line in block.splitlines() if line.strip()]
    lines = _dedupe([line for line in raw_lines if _looks_like_readable_line(line)], limit=28)
    if not lines:
        default["ocr_note"] = "OCR completed but only low-value structural text was recovered."
        return default
    excerpt = _normalize_text(" ".join(lines[:6]))[:280]
    entities = _extract_entity_lines(lines)
    visible_urls = entities["urls"]
    visible_time_strings = entities["times"]
    visible_location_strings = _dedupe(entities["locations"] + _extract_location_like_lines(lines), limit=10)
    merged_text = "\n".join(lines)
    app_detected = _detect_app(merged_text)
    environment_profile = _detect_environment(file_path.name, width, height, merged_text, source_hint)
    zone_note = ", ".join(zone_hits[:4]) if zone_hits else "none"
    return {
        "lines": lines[:28],
        "excerpt": excerpt,
        "visible_urls": _dedupe(visible_urls, limit=8),
        "visible_time_strings": _dedupe(visible_time_strings, limit=8),
        "visible_location_strings": _dedupe(visible_location_strings, limit=8),
        "app_detected": app_detected,
        "environment_profile": environment_profile,
        "ocr_note": f"OCR zones recovered from: {zone_note}.",
    }


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
        }
    for pattern in MAP_COORD_PATTERNS:
        match = pattern.search(joined.replace(" ", ""))
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
            f"Derived geolocation clue parsed from {'on-screen map content' if 'maps' in joined.lower() else 'visible coordinate text'}; corroborate it with browser history, saved links, or surrounding case context before courtroom use."
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
        }
    lower_joined = joined.lower()
    if any(token in lower_joined for token in ["google maps", "directions", "street view", "nearby", "route overview", "satellite"]):
        return {
            "latitude": None,
            "longitude": None,
            "display": "Map-like screenshot detected",
            "source": "Visual map UI",
            "confidence": 22,
            "note": "Map-style UI markers were detected, but no stable coordinates could be parsed. Preserve the screenshot, OCR text, and browser context for manual venue reasoning.",
        }
    return {
        "latitude": None,
        "longitude": None,
        "display": "Unavailable",
        "source": "Unavailable",
        "confidence": 0,
        "note": "No screenshot-derived geolocation clue recovered.",
    }


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
    name = file_path.name.lower()
    software_l = software.lower()
    if app_detected in {"Google Maps", "Google Earth"} or any("google.com/maps" in url.lower() for url in visible_urls):
        return "Map Screenshot", 84
    if app_detected in {"Chrome", "Safari", "Firefox", "Edge"} and ("http" in " ".join(visible_urls).lower() or "www." in " ".join(visible_urls).lower()):
        return "Browser Screenshot", 78
    if app_detected in {"WhatsApp", "Telegram", "Signal", "Discord", "Facebook", "Instagram"}:
        return "Messaging Export", 80
    if source_type in {"Screenshot", "Screenshot / Export"}:
        confidence = 72
        if "screenshot" in name:
            confidence += 10
        return "Screenshot", min(confidence, 88)
    if source_type == "Messaging Export":
        return "Messaging Export", 78
    if source_type == "Edited / Exported":
        return "Edited / Exported", 72
    if source_type == "Camera Photo":
        return "Camera Photo", 86 if has_exif else 62
    if file_path.suffix.lower() in {".gif", ".bmp"}:
        return "Graphic Asset", 70
    if any(term in software_l for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
        return "Edited / Exported", 76
    if not has_exif and file_path.suffix.lower() == ".png" and width >= height:
        return "Screenshot / Export", 61
    return source_type or "Unknown", 48
