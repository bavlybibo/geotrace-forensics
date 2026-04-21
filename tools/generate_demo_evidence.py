from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image, ImageDraw


def decimal_to_dms_rational(value: float):
    value = abs(value)
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60 * 100)
    return ((degrees, 1), (minutes, 1), (seconds, 100))


def make_image(output: Path, text: str, color: str, timestamp: datetime, lat: float | None, lon: float | None, software: str | None = None):
    image = Image.new("RGB", (1600, 900), color)
    draw = ImageDraw.Draw(image)
    draw.text((50, 50), text, fill="white")

    zeroth_ifd = {
        piexif.ImageIFD.Make: u"GeoTrace Labs",
        piexif.ImageIFD.Model: u"ForensicCam X1",
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: timestamp.strftime("%Y:%m:%d %H:%M:%S"),
    }
    gps_ifd = {}

    if software:
        zeroth_ifd[piexif.ImageIFD.Software] = software

    if lat is not None and lon is not None:
        gps_ifd[piexif.GPSIFD.GPSLatitudeRef] = "N" if lat >= 0 else "S"
        gps_ifd[piexif.GPSIFD.GPSLatitude] = decimal_to_dms_rational(lat)
        gps_ifd[piexif.GPSIFD.GPSLongitudeRef] = "E" if lon >= 0 else "W"
        gps_ifd[piexif.GPSIFD.GPSLongitude] = decimal_to_dms_rational(lon)

    exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    image.save(output, exif=exif_bytes, quality=95)


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "demo_evidence"
    base.mkdir(exist_ok=True)

    now = datetime(2026, 4, 10, 10, 30)
    make_image(base / "cairo_scene.jpg", "Evidence A - Cairo", "#1f4e79", now, 30.0444, 31.2357)
    make_image(base / "giza_scene.jpg", "Evidence B - Giza", "#20435c", now + timedelta(hours=1), 29.9773, 31.1325)
    make_image(base / "edited_scene.jpg", "Evidence C - Edited", "#5f1b29", now + timedelta(hours=2), 29.9792, 31.1342, software="Adobe Photoshop")

    plain = Image.new("RGB", (600, 400), "#353535")
    draw = ImageDraw.Draw(plain)
    draw.text((30, 30), "Evidence D - No EXIF", fill="white")
    plain.save(base / "no_exif.png")

    print(f"Demo evidence generated in: {base}")


if __name__ == "__main__":
    main()
