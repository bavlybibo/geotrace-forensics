from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import exifread
from PIL import Image, ImageStat

try:
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:
    pass

from .gps_utils import dms_to_decimal, format_coordinates


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


def is_supported_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def human_datetime(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
    except Exception:
        return "Unknown"


def extract_file_times(file_path: Path) -> Tuple[str, str]:
    stats = file_path.stat()
    created_ts = getattr(stats, "st_ctime", None)
    modified_ts = getattr(stats, "st_mtime", None)
    return human_datetime(created_ts) if created_ts else "Unknown", human_datetime(modified_ts) if modified_ts else "Unknown"


def extract_basic_image_info(file_path: Path) -> Dict[str, str | int | bool | float]:
    info: Dict[str, str | int | bool | float] = {
        "width": 0,
        "height": 0,
        "format_name": "Unknown",
        "color_mode": "Unknown",
        "has_alpha": False,
        "dpi": "N/A",
        "megapixels": 0.0,
        "aspect_ratio": "Unknown",
        "brightness_mean": 0.0,
    }
    try:
        with Image.open(file_path) as image:
            info["width"] = image.width
            info["height"] = image.height
            info["format_name"] = image.format or file_path.suffix.upper().replace(".", "")
            info["color_mode"] = image.mode
            info["has_alpha"] = "A" in image.mode
            info["megapixels"] = round((image.width * image.height) / 1_000_000, 2) if image.width and image.height else 0.0
            if image.width and image.height:
                info["aspect_ratio"] = f"{image.width}:{image.height}"
            grayscale = image.convert("L")
            stat = ImageStat.Stat(grayscale)
            info["brightness_mean"] = round(float(stat.mean[0]), 2) if stat.mean else 0.0
            dpi = image.info.get("dpi")
            if isinstance(dpi, tuple) and len(dpi) >= 2:
                info["dpi"] = f"{int(dpi[0])} x {int(dpi[1])}"
            elif dpi:
                info["dpi"] = str(dpi)
    except Exception:
        pass
    return info


def compute_perceptual_hash(file_path: Path) -> str:
    try:
        with Image.open(file_path) as image:
            image = image.convert("L").resize((9, 8))
            pixels = list(image.getdata())
        rows = [pixels[i * 9:(i + 1) * 9] for i in range(8)]
        bits = []
        for row in rows:
            for i in range(8):
                bits.append("1" if row[i] > row[i + 1] else "0")
        return f"{int(''.join(bits), 2):016x}"
    except Exception:
        return "0" * 16


def extract_exif(file_path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with file_path.open("rb") as handle:
            tags = exifread.process_file(handle, details=False)
        for tag, value in tags.items():
            data[str(tag)] = str(value)
        data["__raw_tags__"] = tags  # internal use
    except Exception:
        data["__raw_tags__"] = {}
    return data


def infer_timestamp_from_filename(file_name: str) -> Optional[str]:
    patterns = [
        r"(20\d{2})-(\d{2})-(\d{2})\s+at\s+(\d{1,2})\.(\d{2})\.(\d{2})\s*([AP]M)?",
        r"(20\d{2})-(\d{2})-(\d{2})[ _-](\d{2})(\d{2})(\d{2})",
        r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})",
        r"(20\d{2})[._-](\d{2})[._-](\d{2})[ T_-](\d{2})[.:_-](\d{2})[.:_-](\d{2})",
        r"(20\d{2})[-_](\d{2})[-_](\d{2})[-_](\d{1,2})[-_](\d{2})[-_](\d{2})\s*([AP]M)?",
    ]
    for pattern in patterns:
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
    embedded = (
        exif.get("EXIF DateTimeOriginal")
        or exif.get("Image DateTime")
        or exif.get("EXIF DateTimeDigitized")
    )
    if embedded:
        return embedded, "Embedded EXIF"
    if file_path is not None:
        guessed = infer_timestamp_from_filename(file_path.name)
        if guessed:
            return guessed, "Filename Pattern"
        created, modified = extract_file_times(file_path)
        if modified != "Unknown":
            return modified, "Filesystem Modified Time"
        if created != "Unknown":
            return created, "Filesystem Created Time"
    return "Unknown", "Unavailable"


def get_tag(exif: Dict[str, str], *names: str, default: str = "N/A") -> str:
    for name in names:
        value = exif.get(name)
        if value:
            return value
    return default


def extract_device_model(exif: Dict[str, str]) -> Tuple[str, str]:
    make = exif.get("Image Make", "").strip() or "Unknown"
    model = exif.get("Image Model", "").strip() or "Unknown"
    if make != "Unknown" and model != "Unknown":
        return f"{make} {model}".strip(), make
    return model if model != "Unknown" else make, make


def extract_software(exif: Dict[str, str]) -> str:
    return get_tag(exif, "Image Software", default="N/A")


def extract_orientation(exif: Dict[str, str]) -> str:
    value = get_tag(exif, "Image Orientation", default="Unknown")
    return ORIENTATION_MAP.get(value, value)


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
            altitude = float(alt_val.num) / float(alt_val.den)
        return latitude, longitude, altitude, format_coordinates(latitude, longitude)
    except Exception:
        return None, None, None, "Unavailable"


def classify_source(file_path: Path, exif: Dict[str, str], software: str, width: int, height: int) -> str:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    if "screenshot" in name:
        return "Screenshot"
    if "whatsapp image" in name or "telegram" in name or "export" in name:
        return "Messaging Export"
    if suffix in {".png", ".webp"} and not exif:
        return "Screenshot / Export"
    software_lower = software.lower()
    if any(term in software_lower for term in ["photoshop", "lightroom", "snapseed", "canva", "gimp"]):
        return "Edited / Exported"
    if width and height and max(width, height) >= 2000 and exif:
        return "Camera Photo"
    if suffix in {".gif", ".bmp"}:
        return "Graphic Asset"
    return "Unknown"


def build_metadata_summary(exif: Dict[str, str]) -> Dict[str, str]:
    return {
        "camera_make": get_tag(exif, "Image Make", default="Unknown"),
        "lens_model": get_tag(exif, "EXIF LensModel", "EXIF LensSpecification", default="N/A"),
        "iso": get_tag(exif, "EXIF ISOSpeedRatings", default="N/A"),
        "exposure_time": get_tag(exif, "EXIF ExposureTime", default="N/A"),
        "f_number": get_tag(exif, "EXIF FNumber", default="N/A"),
        "focal_length": get_tag(exif, "EXIF FocalLength", default="N/A"),
        "artist": get_tag(exif, "Image Artist", default="N/A"),
        "copyright_notice": get_tag(exif, "Image Copyright", default="N/A"),
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
