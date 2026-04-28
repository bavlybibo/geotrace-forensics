"""EXIF/GPS/timestamp/payload extraction implementation.

Moved from app.core.exif_service during v12.10.2 organization-only refactor.
The old module path remains available as a compatibility facade.
"""

from __future__ import annotations

import logging
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import exifread
except Exception:  # pragma: no cover
    exifread = None

from PIL import ExifTags, Image, ImageSequence, ImageStat, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception as exc:
    logging.getLogger("geotrace.exif_service").debug("Optional HEIF opener unavailable: %s", exc)

from ..gps_utils import dms_to_decimal, format_coordinates, gps_confidence_summary

LOGGER = logging.getLogger("geotrace.exif_service")


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
    ".webp",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
}

ORIENTATION_MAP = {
    "1": "Normal",
    "2": "Mirrored Horizontal",
    "3": "Rotated 180°",
    "4": "Mirrored Vertical",
    "5": "Mirrored Horizontal + Rotated 270°",
    "6": "Rotated 90° CW",
    "7": "Mirrored Horizontal + Rotated 90° CW",
    "8": "Rotated 270° CW",
}

SIGNATURE_MAP = {
    b"\x89PNG\r\n\x1a\n": ("PNG", "PNG signature"),
    b"\xff\xd8\xff": ("JPEG", "JPEG SOI"),
    b"GIF87a": ("GIF", "GIF87a"),
    b"GIF89a": ("GIF", "GIF89a"),
    b"BM": ("BMP", "BMP header"),
    b"II*\x00": ("TIFF", "TIFF little-endian"),
    b"MM\x00*": ("TIFF", "TIFF big-endian"),
}

EXTENSION_FAMILY = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".gif": "GIF",
    ".heic": "HEIC",
    ".heif": "HEIF",
}

PIL_TAGS = {int(tag): name for tag, name in ExifTags.TAGS.items()}
GPS_TAGS = {int(tag): name for tag, name in ExifTags.GPSTAGS.items()}


TIMESTAMP_PATTERNS = [
    r"(20\d{2})-(\d{2})-(\d{2})\s+at\s+(\d{1,2})\.(\d{2})\.(\d{2})\s*([AP]M)?",
    r"(20\d{2})-(\d{2})-(\d{2})[ _-](\d{2})(\d{2})(\d{2})",
    r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})",
    r"(20\d{2})[._-](\d{2})[._-](\d{2})[ T_-](\d{2})[.:_-](\d{2})[.:_-](\d{2})",
    r"(20\d{2})[-_](\d{2})[-_](\d{2})[-_](\d{1,2})[-_](\d{2})[-_](\d{2})\s*([AP]M)?",
]


def is_supported_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def human_datetime(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
    except Exception as exc:
        LOGGER.debug("Failed to format timestamp %r: %s", timestamp, exc)
        return "Unknown"


def extract_file_times(file_path: Path) -> Tuple[str, str, str]:
    stats = file_path.stat()
    modified_ts = getattr(stats, "st_mtime", None)
    modified = human_datetime(modified_ts) if modified_ts else "Unknown"

    birth_ts = getattr(stats, "st_birthtime", None)
    if birth_ts:
        return human_datetime(birth_ts), modified, "Filesystem birth time reported by the operating system."

    if sys.platform.startswith("win"):
        created_ts = getattr(stats, "st_ctime", None)
        if created_ts:
            return human_datetime(created_ts), modified, "Filesystem creation time reported by Windows."

    change_ts = getattr(stats, "st_ctime", None)
    change_hint = human_datetime(change_ts) if change_ts else "Unknown"
    return (
        "Unavailable",
        modified,
        f"Filesystem birth/creation time is unavailable on this platform. The closest available value is ctime={change_hint}, which represents metadata-change time and is not treated as creation time.",
    )


def sniff_file_signature(file_path: Path) -> Tuple[str, str]:
    try:
        head = file_path.read_bytes()[:32]
    except Exception as exc:
        LOGGER.warning("Unable to read file signature for %s: %s", file_path, exc)
        return "Unknown", "Unreadable"

    for prefix, resolved in SIGNATURE_MAP.items():
        if head.startswith(prefix):
            return resolved

    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP", "RIFF/WEBP"

    if len(head) >= 16 and head[4:8] == b"ftyp":
        brand = head[8:16].decode("latin1", errors="ignore").strip("\x00 ")
        if "heic" in brand.lower():
            return "HEIC", f"ISO BMFF/{brand}"
        if "heif" in brand.lower() or "mif1" in brand.lower():
            return "HEIF", f"ISO BMFF/{brand}"

    return "Unknown", "Unknown"


def signature_status_for_extension(file_path: Path, signature_family: str) -> str:
    expected = EXTENSION_FAMILY.get(file_path.suffix.lower(), "Unknown")
    if expected == "Unknown" and signature_family == "Unknown":
        return "Unknown"
    if signature_family == "Unknown":
        return "Unknown"
    if expected == signature_family:
        return "Matched"
    if expected == "HEIC" and signature_family in {"HEIC", "HEIF"}:
        return "Compatible"
    if expected == "HEIF" and signature_family in {"HEIF", "HEIC"}:
        return "Compatible"
    return "Mismatch"


def format_trust_from_status(signature_status: str, parser_status: str) -> str:
    if signature_status == "Mismatch":
        return "Conflict"
    if parser_status == "Failed":
        return "Header-only" if signature_status in {"Matched", "Compatible"} else "Weak"
    if signature_status in {"Matched", "Compatible"}:
        return "Verified"
    return "Weak"


def extract_basic_image_info(file_path: Path) -> Dict[str, str | int | bool | float]:
    signature_family, signature_label = sniff_file_signature(file_path)
    inferred_format = EXTENSION_FAMILY.get(file_path.suffix.lower(), file_path.suffix.upper().replace(".", "") or "Unknown")
    info: Dict[str, str | int | bool | float] = {
        "width": 0,
        "height": 0,
        "format_name": inferred_format,
        "color_mode": "Unknown",
        "has_alpha": False,
        "dpi": "N/A",
        "megapixels": 0.0,
        "aspect_ratio": "Unknown",
        "brightness_mean": 0.0,
        "parser_status": "Failed",
        "preview_status": "Unavailable",
        "structure_status": "Suspicious",
        "format_signature": signature_label,
        "format_trust": "Weak",
        "signature_status": signature_status_for_extension(file_path, signature_family),
        "parse_error": "",
        "frame_count": 1,
        "is_animated": False,
        "animation_duration_ms": 0,
    }
    try:
        with Image.open(file_path) as image:
            image.load()
            info["parser_status"] = "Valid"
            info["width"] = image.width
            info["height"] = image.height
            info["format_name"] = image.format or inferred_format
            info["color_mode"] = image.mode
            info["has_alpha"] = "A" in image.mode
            info["megapixels"] = round((image.width * image.height) / 1_000_000, 2) if image.width and image.height else 0.0
            if image.width and image.height:
                info["aspect_ratio"] = f"{image.width}:{image.height}"
            preview_frame = image
            if getattr(image, "is_animated", False):
                info["is_animated"] = True
                info["frame_count"] = max(1, int(getattr(image, "n_frames", 1)))
                info["structure_status"] = "Animated"
                preview_frame = next(iter(ImageSequence.Iterator(image))).copy()
                duration = image.info.get("duration")
                if isinstance(duration, (int, float)):
                    info["animation_duration_ms"] = int(duration) * int(info["frame_count"])
                info["preview_status"] = "First Frame"
            else:
                info["preview_status"] = "Ready"
                info["structure_status"] = "Valid"
            grayscale = preview_frame.convert("L")
            stat = ImageStat.Stat(grayscale)
            info["brightness_mean"] = round(float(stat.mean[0]), 2) if stat.mean else 0.0
            info["format_trust"] = format_trust_from_status(str(info["signature_status"]), str(info["parser_status"]))
            dpi = image.info.get("dpi")
            if isinstance(dpi, tuple) and len(dpi) >= 2:
                info["dpi"] = f"{int(dpi[0])} x {int(dpi[1])}"
            elif dpi:
                info["dpi"] = str(dpi)
    except UnidentifiedImageError as exc:
        info["parse_error"] = f"Unsupported or malformed image structure: {exc.__class__.__name__}"
        info["parser_status"] = "Failed"
        info["structure_status"] = "Corrupt"
    except Exception as exc:
        info["parse_error"] = f"Decoder failure: {exc.__class__.__name__}"
        info["parser_status"] = "Failed"
        info["structure_status"] = "Corrupt"

    if info["signature_status"] == "Mismatch" and info["structure_status"] == "Valid":
        info["structure_status"] = "Suspicious"
    if info["parser_status"] == "Failed":
        info["preview_status"] = "Decoder Failed"
        info["format_trust"] = format_trust_from_status(str(info["signature_status"]), str(info["parser_status"]))
        if not info["parse_error"]:
            info["parse_error"] = f"The file could not be rendered by Pillow. Extension suggests {inferred_format}; signature says {signature_label}."
        if file_path.suffix.lower() == ".png" and file_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n":
            info["parse_error"] += " PNG signature is present but the chunk structure appears incomplete or malformed."
    if info["signature_status"] == "Matched" and info["parser_status"] == "Valid" and signature_family != "Unknown" and inferred_format == "Unknown":
        info["format_name"] = signature_family
    return info


def compute_perceptual_hash(file_path: Path) -> str:
    try:
        with Image.open(file_path) as image:
            if getattr(image, "is_animated", False):
                image.seek(0)
            reduced = image.convert("L").resize((9, 8))
            pixels = list(reduced.getdata())
        rows = [pixels[i * 9:(i + 1) * 9] for i in range(8)]
        bits = []
        for row in rows:
            for idx in range(8):
                bits.append("1" if row[idx] > row[idx + 1] else "0")
        return f"{int(''.join(bits), 2):016x}"
    except Exception:
        return "0" * 16


def _stringify_value(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip("\x00 ")
    if isinstance(value, tuple):
        return ", ".join(_stringify_value(item) for item in value)
    return str(value)


def _flatten_pillow_exif(image: Image.Image) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        exif_block = image.getexif()
    except Exception:
        exif_block = None
    if not exif_block:
        return out
    gps_raw = None
    for tag_id, value in exif_block.items():
        tag_name = PIL_TAGS.get(int(tag_id), str(tag_id))
        if tag_name == "GPSInfo" and isinstance(value, dict):
            gps_raw = value
            for gps_id, gps_value in value.items():
                gps_name = GPS_TAGS.get(int(gps_id), str(gps_id))
                out[f"GPS {gps_name}"] = _stringify_value(gps_value)
        else:
            out[tag_name] = _stringify_value(value)
    if gps_raw is not None:
        out["__pil_gps__"] = gps_raw  # type: ignore[assignment]
    return out


def extract_exif(file_path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    raw_tags: dict = {}
    warnings: List[str] = []

    if exifread is not None:
        try:
            with file_path.open("rb") as handle:
                tags = exifread.process_file(handle, details=False)
            raw_tags = tags
            for tag, value in tags.items():
                data[str(tag)] = str(value)
        except Exception as exc:
            warnings.append(f"EXIF parsing via exifread failed: {exc.__class__.__name__}")
    else:
        warnings.append("exifread is not installed; using Pillow/container fallback only")

    try:
        with Image.open(file_path) as image:
            pillow_meta = _flatten_pillow_exif(image)
            for key, value in pillow_meta.items():
                if key == "__pil_gps__":
                    raw_tags.setdefault("__pil_gps__", value)
                    continue
                data.setdefault(key, value)
            for key, value in (image.info or {}).items():
                if isinstance(value, tuple) and key == "dpi":
                    data.setdefault("Image DPI", f"{value[0]} x {value[1]}")
                elif isinstance(value, (str, bytes, int, float)):
                    rendered = _stringify_value(value)
                    if rendered:
                        data.setdefault(f"ImageInfo {key}", rendered[:240])
            if hasattr(image, "text") and isinstance(getattr(image, "text"), dict):
                for key, value in image.text.items():
                    rendered = _stringify_value(value)
                    if rendered:
                        data.setdefault(f"PNG {key}", rendered[:280])
    except Exception as exc:
        LOGGER.debug("Non-critical EXIF parsing branch failed: %s", exc)

    data["__raw_tags__"] = raw_tags
    if warnings:
        data["__warning__"] = ". ".join(warnings).strip() + "."
    return data


def _entropy_score(blob: bytes) -> float:
    if not blob:
        return 0.0
    counts = {}
    for byte in blob:
        counts[byte] = counts.get(byte, 0) + 1
    total = len(blob)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def _appended_payload_indicator(file_path: Path, blob: bytes) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".png":
        marker = b"IEND\xaeB`\x82"
        idx = blob.rfind(marker)
        if idx >= 0 and idx + len(marker) < len(blob):
            trailing = blob[idx + len(marker):]
            if len(trailing) >= 16:
                return f"Trailing bytes detected after PNG end marker ({len(trailing)} byte(s))."
    if suffix in {".jpg", ".jpeg"}:
        idx = blob.rfind(b"\xff\xd9")
        if idx >= 0 and idx + 2 < len(blob):
            trailing = blob[idx + 2:]
            if len(trailing) >= 16:
                return f"Trailing bytes detected after JPEG end marker ({len(trailing)} byte(s))."
    return ""


def _is_contextual_string(text: str) -> bool:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) < 8:
        return False
    lower = text.lower()
    if lower.startswith(("jfif", "exif", "ihdr", "idat", "iend", "photoshop 3.0")):
        return False
    letters = sum(ch.isalpha() for ch in text)
    digits = sum(ch.isdigit() for ch in text)
    spaces = sum(ch.isspace() for ch in text)
    punct = len(text) - letters - digits - spaces
    alpha_ratio = letters / max(len(text), 1)
    readable_ratio = (letters + digits + spaces) / max(len(text), 1)
    symbol_ratio = punct / max(len(text), 1)
    has_urlish = any(token in lower for token in ["http://", "https://", "www.", ".com", "maps", "token", "secret", "password", "script", "geo", "forensic", "camera", "whatsapp", "telegram"])
    has_word_shape = bool(re.search(r"[aeiou]{1,}|[A-Z][a-z]{2,}|[a-z]{4,}", text))
    repeated_noise = bool(re.search(r"(.)\1{4,}", text))
    if has_urlish:
        return True
    if readable_ratio < 0.76 or symbol_ratio > 0.24:
        return False
    if repeated_noise and not has_word_shape:
        return False
    if punct > max(8, len(text) * 0.22):
        return False
    if alpha_ratio < 0.38 and not has_word_shape:
        return False
    return has_word_shape or spaces > 0


def _classify_payload_blob(blob: bytes) -> tuple[str, str]:
    head = blob[:64].lstrip()
    if head.startswith(b"PK\x03\x04"):
        return "zip", ".zip"
    if head.startswith(b"%PDF"):
        return "pdf", ".pdf"
    if head.startswith((b"<!DOCTYPE html", b"<html", b"<script")) or b"<script" in blob[:256].lower():
        return "html/js", ".html"
    if head.startswith((b"<?xml", b"<svg")) or b"<svg" in blob[:256].lower():
        return "xml/svg", ".xml"
    if head.startswith((b"{", b"[")):
        return "json-like", ".json"
    return "binary-appendix", ".bin"


def _png_chunk_findings(blob: bytes) -> tuple[List[str], List[dict]]:
    findings: List[str] = []
    recoveries: List[dict] = []
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return findings, recoveries

    iend_marker = b"IEND\xaeB`\x82"
    raw_iend_idx = blob.rfind(iend_marker)
    raw_trailing_payload = b""
    raw_payload_offset = -1
    if raw_iend_idx >= 0 and raw_iend_idx + len(iend_marker) < len(blob):
        raw_payload_offset = raw_iend_idx + len(iend_marker)
        raw_trailing_payload = blob[raw_payload_offset:]

    offset = 8
    seen_iend = False
    malformed = False
    while offset + 8 <= len(blob):
        try:
            length = int.from_bytes(blob[offset:offset + 4], "big")
            chunk_type = blob[offset + 4:offset + 8]
            data_start = offset + 8
            data_end = data_start + length
            crc_end = data_end + 4
            if crc_end > len(blob):
                malformed = True
                findings.append("PNG chunk table ends unexpectedly before CRC; container may be truncated or malformed.")
                break
            chunk_name = chunk_type.decode("latin1", errors="ignore")
            if chunk_name in {"tEXt", "zTXt", "iTXt"}:
                findings.append(f"PNG metadata chunk present: {chunk_name} ({length} byte(s)).")
            if chunk_name == "IEND":
                seen_iend = True
                if crc_end < len(blob):
                    payload = blob[crc_end:]
                    findings.insert(0, f"Trailing bytes detected after PNG end marker ({len(payload)} byte(s)).")
                    kind, ext = _classify_payload_blob(payload)
                    recoveries.append({
                        "offset": crc_end,
                        "length": len(payload),
                        "kind": kind,
                        "extension": ext,
                        "label": f"Appended {kind} payload after PNG IEND",
                        "bytes": payload,
                    })
                break
            offset = crc_end
        except Exception:
            malformed = True
            findings.append("PNG chunk parsing aborted due to malformed structure.")
            break

    if not seen_iend and raw_trailing_payload:
        findings.insert(0, f"Trailing bytes detected after PNG end marker ({len(raw_trailing_payload)} byte(s)).")
        kind, ext = _classify_payload_blob(raw_trailing_payload)
        recoveries.append({
            "offset": raw_payload_offset,
            "length": len(raw_trailing_payload),
            "kind": kind,
            "extension": ext,
            "label": f"Appended {kind} payload after raw PNG end marker",
            "bytes": raw_trailing_payload,
        })
        seen_iend = True

    if not seen_iend:
        findings.append("PNG IEND chunk was not found; container may be malformed or intentionally crafted.")
    elif malformed:
        findings.append("PNG structure is malformed even though an end marker was found; treat appended/trailing bytes as a manual-review finding.")
    return findings, recoveries


def _jpeg_tail_findings(blob: bytes) -> tuple[List[str], List[dict]]:
    findings: List[str] = []
    recoveries: List[dict] = []
    idx = blob.rfind(b"\xff\xd9")
    if idx >= 0 and idx + 2 < len(blob):
        payload = blob[idx + 2:]
        findings.append(f"Trailing bytes exist after JPEG end marker ({len(payload)} byte(s)).")
        kind, ext = _classify_payload_blob(payload)
        recoveries.append({
            "offset": idx + 2,
            "length": len(payload),
            "kind": kind,
            "extension": ext,
            "label": f"Appended {kind} payload after JPEG EOI",
            "bytes": payload,
        })
    return findings, recoveries


def _inline_payload_findings(blob: bytes) -> tuple[List[str], List[dict]]:
    findings: List[str] = []
    recoveries: List[dict] = []
    signatures = [
        (b"PK\x03\x04", "zip", ".zip", "ZIP archive signature"),
        (b"%PDF", "pdf", ".pdf", "PDF signature"),
        (b"<script", "html/js", ".html", "HTML/JavaScript marker"),
        (b"<html", "html/js", ".html", "HTML marker"),
        (b"<?xml", "xml/svg", ".xml", "XML marker"),
        (b"<svg", "xml/svg", ".xml", "SVG/XML marker"),
    ]
    seen_offsets = set()
    for token, kind, ext, label in signatures:
        idx = blob.find(token)
        if idx <= 16 or idx in seen_offsets:
            continue
        payload = blob[idx:]
        if len(payload) < 24:
            continue
        seen_offsets.add(idx)
        findings.append(f"Embedded {label} detected inside the container at offset {idx} ({len(payload)} byte(s) to EOF).")
        recoveries.append({
            "offset": idx,
            "length": len(payload),
            "kind": kind,
            "extension": ext,
            "label": f"Inline {kind} payload from offset {idx}",
            "bytes": payload,
        })
    return findings, recoveries


def extract_embedded_text_hints(file_path: Path, format_name: str = "Unknown") -> Dict[str, object]:
    try:
        blob = file_path.read_bytes()
    except Exception:
        return {
            "strings": [],
            "context_strings": [],
            "code_indicators": [],
            "payload_markers": [],
            "suspicious_embeds": [],
            "summary": "The file bytes could not be read for hidden-content scanning.",
            "context_summary": "Embedded text and hidden-code scan unavailable.",
            "overview": "Embedded text and hidden-code scan unavailable.",
            "urls": [],
            "finding_types": [],
            "stego_suspicion": "Hidden-content scan unavailable because the file could not be read.",
            "container_findings": [],
            "recoverable_segments": [],
            "carved_summary": "No carved payload segments were recovered.",
        }

    if not blob:
        return {
            "strings": [],
            "context_strings": [],
            "code_indicators": [],
            "payload_markers": [],
            "suspicious_embeds": [],
            "summary": "No byte content was available for hidden-content scanning.",
            "context_summary": "Embedded text and hidden-code scan unavailable.",
            "overview": "Embedded text and hidden-code scan unavailable.",
            "urls": [],
            "finding_types": [],
            "stego_suspicion": "No byte content was available for hidden-content scanning.",
            "container_findings": [],
            "recoverable_segments": [],
            "carved_summary": "No carved payload segments were recovered.",
        }

    ascii_strings = [s.decode("utf-8", errors="ignore").strip() for s in re.findall(rb"[\x20-\x7e]{8,}", blob)]
    cleaned: List[str] = []
    seen = set()
    noise_count = 0
    for item in ascii_strings:
        item = re.sub(r"\s+", " ", item).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        if _is_contextual_string(item):
            cleaned.append(item)
        else:
            noise_count += 1

    urls: List[str] = []
    seen_urls = set()
    for item in cleaned:
        for match in re.findall(r'''https?://[^\s"'<>]+''', item, flags=re.IGNORECASE):
            if match not in seen_urls:
                seen_urls.add(match)
                urls.append(match)

    suspicious_patterns = [
        (r"<script\b", "HTML/JavaScript <script> marker", "script"),
        (r"javascript:", "javascript: URI payload", "script"),
        (r"<svg\b", "SVG/vector payload marker", "svg"),
        (r"onload=|onerror=", "HTML event-handler payload marker", "script"),
        (r"<\?php", "PHP code marker", "code"),
        (r"eval\(", "eval() marker", "code"),
        (r"document\.cookie|localStorage|sessionStorage", "browser data access marker", "browser-data"),
        (r"powershell|cmd\.exe|/bin/bash|curl\s|wget\s", "shell / command execution marker", "command"),
        (r"base64,|frombase64string|atob\(", "base64 payload marker", "encoded"),
        (r"import\s+os|subprocess\.|__import__", "Python execution marker", "code"),
        (r"SELECT\s+.+FROM|UNION\s+SELECT", "SQL payload marker", "sql"),
        (r"token=|api[_-]?key|secret|password=|authorization:", "credential/token marker", "credential"),
        (r"-----BEGIN [A-Z ]+-----", "embedded key / certificate block", "credential"),
    ]

    code_indicators: List[str] = []
    context_strings: List[str] = []
    suspicious_embeds: List[str] = []
    payload_markers: List[str] = []
    finding_types: List[str] = []

    for item in cleaned:
        lower = item.lower()
        matched = False
        for pattern, label, finding_type in suspicious_patterns:
            if re.search(pattern, item, flags=re.IGNORECASE):
                indicator = f"{label}: {item[:140]}"
                if indicator not in code_indicators:
                    code_indicators.append(indicator)
                if finding_type not in finding_types:
                    finding_types.append(finding_type)
                matched = True
        if matched:
            payload_markers.append(item[:160])
        if re.search(r"[A-Za-z0-9+/]{80,}={0,2}", item):
            suspicious_embeds.append(f"Long encoded-looking blob: {item[:120]}")
            if "encoded" not in finding_types:
                finding_types.append("encoded")
        if any(token in lower for token in ["http://", "https://", "token", "secret", "password", "script"]):
            context_strings.append(item[:180])
        elif len(context_strings) < 12:
            context_strings.append(item[:120])

    container_findings: List[str] = []
    recoveries: List[dict] = []
    if file_path.suffix.lower() == ".png":
        extra_findings, extra_recoveries = _png_chunk_findings(blob)
        container_findings.extend(extra_findings)
        recoveries.extend(extra_recoveries)
    elif file_path.suffix.lower() in {".jpg", ".jpeg"}:
        extra_findings, extra_recoveries = _jpeg_tail_findings(blob)
        container_findings.extend(extra_findings)
        recoveries.extend(extra_recoveries)
    else:
        appended = _appended_payload_indicator(file_path, blob)
        if appended:
            container_findings.append(appended)

    inline_findings, inline_recoveries = _inline_payload_findings(blob)
    for finding in inline_findings:
        if finding not in container_findings:
            container_findings.append(finding)
    existing_offsets = {(item.get("offset"), item.get("kind")) for item in recoveries}
    for recovery in inline_recoveries:
        key = (recovery.get("offset"), recovery.get("kind"))
        if key not in existing_offsets:
            recoveries.append(recovery)
            existing_offsets.add(key)

    for finding in container_findings:
        if finding not in suspicious_embeds:
            suspicious_embeds.append(finding)
        if "append" in finding.lower() or "trailing" in finding.lower():
            if "container-appendix" not in finding_types:
                finding_types.append("container-appendix")
        if "chunk" in finding.lower() and "chunk-metadata" not in finding_types:
            finding_types.append("chunk-metadata")

    tail = blob[-4096:] if len(blob) > 4096 else blob
    entropy = _entropy_score(tail)
    stego_suspicion = "No strong steganography or appended-payload indicator was detected."
    if recoveries and entropy >= 7.4:
        stego_suspicion = f"High-entropy trailing data suggests appended payload or stego-like packing (entropy {entropy:.2f})."
    elif recoveries:
        stego_suspicion = "Recoverable trailing/appended data exists after the logical image ending. Treat it as a hidden payload candidate until explained."
    elif entropy >= 7.75 and file_path.suffix.lower() in {".png", ".bmp"}:
        stego_suspicion = f"Late-file entropy is elevated ({entropy:.2f}); no payload was confirmed, but deeper stego review could be justified."

    format_hint = str(format_name or file_path.suffix.upper().replace(".", "") or "Unknown")
    if file_path.suffix.lower() == ".svg" or any("<svg" in s.lower() for s in cleaned[:8]):
        code_indicators.insert(0, "SVG content can legally contain scripts, hyperlinks, CSS, and embedded XML payloads.")
        if "svg" not in finding_types:
            finding_types.insert(0, "svg")

    code_indicators = code_indicators[:12]
    payload_markers = payload_markers[:12]
    suspicious_embeds = suspicious_embeds[:8]
    context_strings = context_strings[:12] if context_strings else cleaned[:12]

    if code_indicators or suspicious_embeds:
        summary = (
            f"Tiered hidden-content scanning found {len(code_indicators)} code/payload marker(s), {len(suspicious_embeds)} structural warning(s), "
            f"and {len(recoveries)} recoverable segment(s). Treat this as heuristic evidence until manual validation confirms the payload context."
        )
        overview = (
            f"Embedded text scan for {format_hint}: {len(cleaned)} readable string(s), {len(code_indicators)} marker(s), "
            f"{len(suspicious_embeds)} structural warning(s), {len(recoveries)} recoverable segment(s)."
        )
    elif cleaned:
        summary = (
            f"Readable embedded strings were recovered from the {format_hint} container, but no strong script/code markers were detected. "
            f"These strings are kept for analyst context only and are not treated as hidden-code hits by default."
        )
        overview = f"Embedded text scan for {format_hint}: {len(cleaned)} analyst-readable string(s) recovered with no strong code markers."
    else:
        summary = f"No readable embedded strings or code-like markers were recovered from the {format_hint} container."
        overview = "No embedded text payloads or code-like markers were detected."

    noise_class = "low" if noise_count < 40 else "moderate" if noise_count < 140 else "heavy"
    context_summary = (
        f"Tier 1 analyst-readable context: {min(len(cleaned), 12)}. Tier 2 suspicious embeds: {len(suspicious_embeds)}. "
        f"Tier 3 payload/code markers: {len(code_indicators)}. Structural noise filtered: {noise_count} ({noise_class})."
    )
    carved_summary = (
        f"Recoverable payload segments identified: {len(recoveries)}. "
        f"Primary types: {', '.join(item['kind'] for item in recoveries[:3]) if recoveries else 'none'}."
    )
    return {
        "strings": context_strings[:12],
        "context_strings": context_strings[:12],
        "code_indicators": code_indicators,
        "payload_markers": payload_markers,
        "suspicious_embeds": suspicious_embeds,
        "summary": summary,
        "context_summary": context_summary,
        "overview": overview,
        "urls": urls[:12],
        "finding_types": finding_types[:10],
        "stego_suspicion": stego_suspicion,
        "container_findings": container_findings[:8],
        "recoverable_segments": recoveries[:4],
        "carved_summary": carved_summary,
    }


def infer_timestamp_from_filename(file_name: str) -> Optional[str]:
    for pattern in TIMESTAMP_PATTERNS:
        match = re.search(pattern, file_name, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            parts = list(match.groups())
            meridiem = None
            if len(parts) == 7:
                meridiem = parts.pop()
            year, month, day, hour, minute, second = parts
            hour_i = int(hour)
            if meridiem:
                meridiem = meridiem.upper()
                if meridiem == "PM" and hour_i != 12:
                    hour_i += 12
                elif meridiem == "AM" and hour_i == 12:
                    hour_i = 0
            dt = datetime(int(year), int(month), int(day), hour_i, int(minute), int(second))
            return dt.strftime("%Y:%m:%d %H:%M:%S")
        except Exception:
            continue
    return None


def extract_timestamp(exif: Dict[str, str], file_path: Path | None = None) -> Tuple[str, str]:
    if exif.get("EXIF DateTimeOriginal"):
        return exif["EXIF DateTimeOriginal"], "Native EXIF Original"
    if exif.get("DateTimeOriginal"):
        return exif["DateTimeOriginal"], "Native EXIF Original"
    if exif.get("Image DateTime"):
        return exif["Image DateTime"], "Embedded EXIF"
    if exif.get("DateTime"):
        return exif["DateTime"], "Embedded EXIF"
    if exif.get("EXIF DateTimeDigitized"):
        return exif["EXIF DateTimeDigitized"], "Embedded EXIF Digitized"
    if exif.get("DateTimeDigitized"):
        return exif["DateTimeDigitized"], "Embedded EXIF Digitized"
    if file_path is not None:
        guessed = infer_timestamp_from_filename(file_path.name)
        if guessed:
            return guessed, "Filename Pattern"
        created, modified, _ = extract_file_times(file_path)
        if modified != "Unknown":
            return modified, "Filesystem Modified Time"
        if created != "Unavailable":
            return created, "Filesystem Birth / Creation Time"
    return "Unknown", "Unavailable"


def infer_timestamp_from_text(text: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    patterns = [
        r"(20\d{2})[-/:.](\d{2})[-/:.](\d{2})[ T](\d{1,2})[:.](\d{2})(?::(\d{2}))?",
        r"(20\d{2})[-_](\d{2})[-_](\d{2})[ _-](\d{2})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month, day, hour, minute, second = match.groups(default="00")
        try:
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
            return dt.strftime("%Y:%m:%d %H:%M:%S")
        except Exception:
            continue
    return None


def build_time_assessment(exif: Dict[str, str], file_path: Path, visible_time_strings: List[str] | None = None) -> Dict[str, object]:
    visible_time_strings = visible_time_strings or []
    candidates: List[tuple[str, str, int]] = []
    for key, label, score in [
        ("EXIF DateTimeOriginal", "Native EXIF Original", 94),
        ("DateTimeOriginal", "Native EXIF Original", 94),
        ("Image DateTime", "Embedded EXIF", 84),
        ("DateTime", "Embedded EXIF", 84),
        ("EXIF DateTimeDigitized", "Embedded EXIF Digitized", 82),
        ("DateTimeDigitized", "Embedded EXIF Digitized", 82),
    ]:
        if exif.get(key):
            candidates.append((exif[key], label, score))
    guessed = infer_timestamp_from_filename(file_path.name)
    if guessed:
        candidates.append((guessed, "Filename Pattern", 58))
    for visible in visible_time_strings:
        inferred = infer_timestamp_from_text(visible) or infer_timestamp_from_filename(visible)
        if inferred:
            candidates.append((inferred, "Visible On-Screen Time", 52))
            break
    created, modified, _ = extract_file_times(file_path)
    if modified != "Unknown":
        candidates.append((modified, "Filesystem Modified Time", 42))
    if created != "Unavailable":
        candidates.append((created, "Filesystem Birth / Creation Time", 38))

    if not candidates:
        confidence, verdict = evaluate_timestamp_confidence("Unknown", "Unavailable")
        return {
            "timestamp": "Unknown",
            "source": "Unavailable",
            "confidence": confidence,
            "verdict": verdict,
            "candidates": [],
            "conflicts": ["No trusted time candidate was recovered from EXIF, visible text, filename, or filesystem metadata."],
        }

    candidates = sorted(candidates, key=lambda item: item[2], reverse=True)
    best = candidates[0]
    conflicts: List[str] = []

    def _parse_dt(raw: str):
        try:
            return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        except Exception:
            return None

    best_dt = _parse_dt(best[0])
    for value, source, _ in candidates[1:]:
        dt = _parse_dt(value)
        if best_dt is not None and dt is not None and abs((best_dt - dt).total_seconds()) > 12 * 3600:
            conflicts.append(f"{source} differs materially from the selected anchor ({best[1]}).")
    confidence, verdict = evaluate_timestamp_confidence(best[0], best[1])
    if conflicts:
        verdict += " Conflicts were also observed across weaker time candidates, so external corroboration is recommended."
    return {
        "timestamp": best[0],
        "source": best[1],
        "confidence": confidence,
        "verdict": verdict,
        "candidates": [f"{source}: {value}" for value, source, _ in candidates],
        "conflicts": conflicts,
    }


def get_tag(exif: Dict[str, str], *names: str, default: str = "N/A") -> str:
    for name in names:
        value = exif.get(name)
        if value:
            return value
    return default


def extract_device_model(exif: Dict[str, str]) -> Tuple[str, str]:
    make = get_tag(exif, "Image Make", "Make", default="Unknown").strip() or "Unknown"
    model = get_tag(exif, "Image Model", "Model", default="Unknown").strip() or "Unknown"
    if make != "Unknown" and model != "Unknown":
        return f"{make} {model}".strip(), make
    return model if model != "Unknown" else make, make


def extract_software(exif: Dict[str, str]) -> str:
    return get_tag(exif, "Image Software", "Software", default="N/A")


def extract_orientation(exif: Dict[str, str]) -> str:
    value = get_tag(exif, "Image Orientation", "Orientation", default="Unknown")
    return ORIENTATION_MAP.get(value, value)


def _safe_fraction(value) -> float:
    if hasattr(value, "num") and hasattr(value, "den"):
        try:
            return float(value.num) / float(value.den)
        except Exception:
            return 0.0
    if isinstance(value, tuple) and len(value) >= 2:
        try:
            return float(value[0]) / float(value[1])
        except Exception:
            return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _parse_gps_string(value: str) -> List[float]:
    return [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", value or "")[:3]]


def extract_gps(exif: Dict[str, str]):
    tags = exif.get("__raw_tags__", {})
    try:
        lat_values = tags["GPS GPSLatitude"].values
        lat_ref = str(tags["GPS GPSLatitudeRef"])
        lon_values = tags["GPS GPSLongitude"].values
        lon_ref = str(tags["GPS GPSLongitudeRef"])
        latitude = dms_to_decimal(lat_values, lat_ref)
        longitude = dms_to_decimal(lon_values, lon_ref)
        altitude = None
        if "GPS GPSAltitude" in tags:
            alt_val = tags["GPS GPSAltitude"].values[0]
            altitude = _safe_fraction(alt_val)
        return latitude, longitude, altitude, format_coordinates(latitude, longitude)
    except Exception as exc:
        LOGGER.debug("Non-critical EXIF parsing branch failed: %s", exc)

    pil_gps = tags.get("__pil_gps__") if isinstance(tags, dict) else None
    if isinstance(pil_gps, dict):
        try:
            lat_values = pil_gps.get(2)
            lat_ref = str(pil_gps.get(1, "N"))
            lon_values = pil_gps.get(4)
            lon_ref = str(pil_gps.get(3, "E"))
            if lat_values and lon_values:
                latitude = dms_to_decimal(lat_values, lat_ref)
                longitude = dms_to_decimal(lon_values, lon_ref)
                altitude = _safe_fraction(pil_gps.get(6)) if pil_gps.get(6) is not None else None
                return latitude, longitude, altitude, format_coordinates(latitude, longitude)
        except Exception as exc:
            LOGGER.debug("Non-critical EXIF parsing branch failed: %s", exc)

    try:
        lat_text = exif.get("GPS GPSLatitude")
        lon_text = exif.get("GPS GPSLongitude")
        if lat_text and lon_text:
            lat_ref = exif.get("GPS GPSLatitudeRef", "N")
            lon_ref = exif.get("GPS GPSLongitudeRef", "E")
            latitude = dms_to_decimal(_parse_gps_string(lat_text), lat_ref)
            longitude = dms_to_decimal(_parse_gps_string(lon_text), lon_ref)
            altitude = None
            if exif.get("GPS GPSAltitude"):
                alt_values = _parse_gps_string(exif.get("GPS GPSAltitude", ""))
                altitude = alt_values[0] if alt_values else None
            return latitude, longitude, altitude, format_coordinates(latitude, longitude)
    except Exception as exc:
        LOGGER.debug("Non-critical EXIF parsing branch failed: %s", exc)
    return None, None, None, "Unavailable"


def evaluate_timestamp_confidence(timestamp: str, source: str) -> Tuple[int, str]:
    if timestamp == "Unknown" or source == "Unavailable":
        return 0, "No trusted time anchor was recovered from EXIF, filename, or filesystem metadata."
    if source == "Native EXIF Original":
        return 94, "Timestamp came from EXIF DateTimeOriginal, which is the strongest native time anchor available in this workflow."
    if source.startswith("Embedded EXIF"):
        return 84, "Timestamp came from embedded EXIF metadata but not the strongest original-capture tag."
    if source == "Filename Pattern":
        return 58, "Timestamp was inferred from the filename. Use it for triage, but corroborate it before courtroom use."
    if source.startswith("Filesystem"):
        return 42, "Timestamp came from filesystem metadata, which can drift after copying, syncing, or export operations."
    return 30, "Timestamp source is weak or inferred and needs external corroboration."


def evaluate_gps_details(exif: Dict[str, str], latitude: float | None, longitude: float | None, altitude: float | None, source_type: str) -> Tuple[str, int, str]:
    gps_source = "Native EXIF" if latitude is not None and longitude is not None else "Unavailable"
    confidence, note = gps_confidence_summary(
        latitude,
        longitude,
        source=gps_source,
        altitude=altitude,
        exif_present=bool(exif),
        source_type=source_type,
    )
    return gps_source, confidence, note


def classify_source(file_path: Path, exif: Dict[str, str], software: str, width: int, height: int, parser_status: str = "Valid") -> str:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    software_lower = (software or "").lower()
    if parser_status == "Failed":
        return "Malformed / Unsupported Asset"
    if any(term in software_lower for term in ["photoshop", "lightroom", "snapseed", "canva", "gimp"]):
        return "Edited / Exported"
    if exif and suffix in {".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif"} and max(width, height) >= 1200:
        return "Camera Photo"
    if "screenshot" in name:
        return "Screenshot"
    if "whatsapp image" in name or "telegram" in name or "export" in name:
        return "Messaging Export"
    if suffix in {".png", ".webp"} and not exif:
        return "Screenshot / Export"
    if suffix in {".gif", ".bmp"}:
        return "Graphic Asset"
    return "Unknown"


def build_metadata_summary(exif: Dict[str, str]) -> Dict[str, str]:
    return {
        "camera_make": get_tag(exif, "Image Make", "Make", default="Unknown"),
        "lens_model": get_tag(exif, "EXIF LensModel", "LensModel", "EXIF LensSpecification", default="N/A"),
        "iso": get_tag(exif, "EXIF ISOSpeedRatings", "ISOSpeedRatings", default="N/A"),
        "exposure_time": get_tag(exif, "EXIF ExposureTime", "ExposureTime", default="N/A"),
        "f_number": get_tag(exif, "EXIF FNumber", "FNumber", default="N/A"),
        "focal_length": get_tag(exif, "EXIF FocalLength", "FocalLength", default="N/A"),
        "artist": get_tag(exif, "Image Artist", "Artist", default="N/A"),
        "copyright_notice": get_tag(exif, "Image Copyright", "Copyright", default="N/A"),
        "orientation": extract_orientation(exif),
    }


def build_osint_leads(
    file_path: Path,
    source_type: str,
    timestamp: str,
    timestamp_source: str,
    device_model: str,
    software: str,
    gps_display: str,
    width: int,
    height: int,
) -> list[str]:
    leads: list[str] = []
    leads.append(f"Preserve original path and hash pair for later chain-of-custody validation: {file_path.name}.")
    if timestamp != "Unknown":
        leads.append(f"Cross-check the recovered time ({timestamp}) against chat logs, upload times, or cloud backups. Source: {timestamp_source}.")
    if device_model not in {"Unknown", "N/A"}:
        leads.append(f"Use device model '{device_model}' as a search pivot when correlating other images from the same source device.")
    if software not in {"N/A", "Unknown", ""}:
        leads.append(f"Software tag '{software}' may indicate export or editing history. Validate whether this matches the alleged acquisition workflow.")
    if gps_display != "Unavailable":
        leads.append(f"Verify GPS coordinates externally and compare with maps, CCTV coverage, or witness statements around {gps_display}.")
    if source_type in {"Messaging Export", "Screenshot", "Screenshot / Export"}:
        leads.append("Messaging-export indicators suggest reduced embedded metadata; prioritize filename patterns, chat context, and filesystem times.")
    if width and height:
        leads.append(f"Resolution profile ({width} x {height}) can help distinguish camera originals from cropped screenshots or reposted media.")
    return leads[:6]
