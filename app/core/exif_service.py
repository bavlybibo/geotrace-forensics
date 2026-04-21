from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import exifread
from PIL import Image

from .gps_utils import dms_to_decimal, format_coordinates


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}


def is_supported_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def extract_basic_image_info(file_path: Path) -> Tuple[int, int]:
    try:
        with Image.open(file_path) as image:
            return image.width, image.height
    except Exception:
        return 0, 0


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


def extract_timestamp(exif: Dict[str, str], file_path: Path | None = None) -> str:
    embedded = (
        exif.get("EXIF DateTimeOriginal")
        or exif.get("Image DateTime")
        or exif.get("EXIF DateTimeDigitized")
    )
    if embedded:
        return embedded
    if file_path is not None:
        guessed = infer_timestamp_from_filename(file_path.name)
        if guessed:
            return guessed
    return "Unknown"


def infer_timestamp_from_filename(file_name: str) -> str | None:
    patterns = [
        # WhatsApp Image 2025-11-10 at 16.02.41_3179e90d.jpg
        (r"(20\d{2})-(\d{2})-(\d{2})\s+at\s+(\d{2})\.(\d{2})\.(\d{2})", "%Y:%m:%d %H:%M:%S"),
        # Screenshot 2026-04-12 143207.png
        (r"(20\d{2})-(\d{2})-(\d{2})[ _-](\d{2})(\d{2})(\d{2})", "%Y:%m:%d %H:%M:%S"),
        # IMG_20260412_143207.jpg
        (r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})", "%Y:%m:%d %H:%M:%S"),
    ]

    for pattern, _ in patterns:
        match = re.search(pattern, file_name, flags=re.IGNORECASE)
        if match:
            year, month, day, hour, minute, second = match.groups()
            try:
                dt = datetime(
                    int(year),
                    int(month),
                    int(day),
                    int(hour),
                    int(minute),
                    int(second),
                )
                return dt.strftime("%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
    return None


def extract_device_model(exif: Dict[str, str]) -> str:
    make = exif.get("Image Make", "").strip()
    model = exif.get("Image Model", "").strip()
    if make and model:
        return f"{make} {model}".strip()
    return model or make or "Unknown"


def extract_software(exif: Dict[str, str]) -> str:
    return exif.get("Image Software", "N/A")


def extract_gps(exif: Dict[str, str]):
    tags = exif.get("__raw_tags__", {})
    try:
        lat_values = tags["GPS GPSLatitude"].values
        lat_ref = str(tags["GPS GPSLatitudeRef"])
        lon_values = tags["GPS GPSLongitude"].values
        lon_ref = str(tags["GPS GPSLongitudeRef"])
        latitude = dms_to_decimal(lat_values, lat_ref)
        longitude = dms_to_decimal(lon_values, lon_ref)
        return latitude, longitude, format_coordinates(latitude, longitude)
    except Exception:
        return None, None, "Unavailable"
