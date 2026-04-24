from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

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
    "mosque", "church", "metro", "university", "school", "tower", "square", "station",
    "cairo", "giza", "heliopolis", "alexandria", "restaurant", "cafe", "venue",
    "مطار", "مستشفى", "مدينة", "شارع", "طريق", "مول", "حديقة", "الزيتون", "المرج",
)

PLACE_SUFFIXES = (
    "tower", "mall", "airport", "station", "bridge", "park", "hospital", "metro", "square",
    "museum", "university", "school", "cafe", "restaurant", "mosque", "church", "district",
    "hotel", "corridor",
)

APP_PATTERNS = [
    ("Google Maps", ["google maps", "maps/@", "google.com/maps", "maps.google", "street view", "directions", "satellite", "route overview", "nearby"]),
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
        if re.search(r"\b(?:st\.?|street|rd\.?|road|ave\.?|avenue|blvd\.?|district|city|park|mall|bridge|tower|station)\b", lower):
            out.append(line)
    return _dedupe(out, limit=10)


def _extract_map_labels(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line).strip(" -:|")
        lower = cleaned.lower()
        if any(keyword in lower for keyword in LOCATION_KEYWORDS):
            out.append(cleaned)
            continue
        words = cleaned.split()
        if len(words) >= 2 and any(words[-1].lower().strip(".,") == suffix for suffix in PLACE_SUFFIXES):
            out.append(cleaned)
    return _dedupe(out, limit=8)


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
        if any(keyword in lower for keyword in LOCATION_KEYWORDS):
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
    if any(token in lower for token in ["google maps", "http", "www.", ".com", "search google maps", "directions", "street view"]):
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
        "ocr_map_labels": [],
    }
    mode = (mode or os.getenv("GEOTRACE_OCR_MODE", "quick")).strip().lower()
    if mode not in {"off", "quick", "deep"}:
        mode = "quick"
    if mode == "off" and not force:
        default["ocr_note"] = "OCR skipped because GEOTRACE_OCR_MODE=off."
        return default
    if cache_dir is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            stat = file_path.stat()
            cache_key = f"{file_path.name}.{stat.st_size}.{int(stat.st_mtime)}.{mode}.{force}.ocr.json"
            cache_path = cache_dir / re.sub(r"[^A-Za-z0-9_.-]+", "_", cache_key)
            if cache_path.exists():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(cached, dict):
                    cached["ocr_note"] = str(cached.get("ocr_note", "OCR loaded from cache.")) + " Cached result."
                    return cached
        except Exception:
            cache_path = None
    else:
        cache_path = None
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
    try:
        with Image.open(file_path) as image:
            image.load()
            work = image.convert("L")
            work = ImageOps.autocontrast(work)
            if max(work.size) < 1700:
                work = work.resize((work.width * 2, work.height * 2))
            zones = [("full", work, "--psm 11")]
            if mode == "deep" or force:
                zones.append(("top", work.crop((0, 0, work.width, max(180, int(work.height * 0.22)))), "--psm 6"))
                zones.append(("bottom", work.crop((0, int(work.height * 0.72), work.width, work.height)), "--psm 6"))
            for zone_name, candidate, config in zones:
                try:
                    block = pytesseract.image_to_string(candidate, config=config, timeout=1.2)
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
        default["raw_text"] = merged[:2500]
        return default
    excerpt = _normalize_text(" ".join(lines[:6]))[:280]
    entity_lines = _extract_entity_lines(lines, merged)
    confidence, relevance = _score_ocr(lines, zone_hits, entity_lines)
    merged_text = "\n".join(lines)
    app_detected = _detect_app(merged_text, entity_lines["app_names"])
    environment_profile = _detect_environment(file_path.name, width, height, merged_text, source_hint)
    zone_note = ", ".join(zone_hits[:4]) if zone_hits else "none"
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
        "ocr_map_labels": entity_lines["map_labels"],
        "environment_profile": environment_profile,
        "ocr_note": f"OCR zones recovered from: {zone_note}. Mode={mode}.",
        "ocr_confidence": confidence,
        "ocr_analyst_relevance": relevance,
    }
    if cache_path is not None:
        try:
            cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except Exception:
            pass
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
    map_labels = _extract_map_labels([line for line in joined.splitlines() if line.strip()])
    location_hits = _extract_location_like_lines([line for line in joined.splitlines() if line.strip()])
    possible_geo_clues = _dedupe(map_labels + location_hits, limit=6)
    if possible_geo_clues:
        best = possible_geo_clues[0]
        confidence = 34 if any(token in lower_joined for token in ["google maps", "directions", "street view", "route overview", "nearby", "satellite"]) else 22
        return {
            "latitude": None,
            "longitude": None,
            "display": f"Possible geo clue: {best}",
            "source": "OCR place label",
            "confidence": confidence,
            "note": "Visible map/place labels suggest a possible geo lead, but no stable coordinates were parsed. Preserve OCR text and application context for manual venue reasoning.",
            "possible_geo_clues": possible_geo_clues,
        }
    if any(token in lower_joined for token in ["google maps", "directions", "street view", "nearby", "route overview", "satellite"]):
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
