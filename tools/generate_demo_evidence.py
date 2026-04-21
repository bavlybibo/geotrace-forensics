from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

try:
    import piexif
except Exception:
    piexif = None


CANVAS = (1664, 909)


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
    draw.text((50, 110), timestamp.strftime("%Y-%m-%d %H:%M:%S"), fill="#dff6ff")

    if piexif is None:
        image.save(output, quality=95)
        return

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


def make_map_screenshot(output: Path, *, title: str, venue: str, road: str, coords: str, hint_url: str, timestamp_label: str):
    image = Image.new("RGB", CANVAS, "#f3f5f9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, CANVAS[0], 68), fill="#1f3f66")
    draw.text((26, 22), title, fill="white")
    draw.rectangle((44, 108, 1620, 832), fill="#e6edf4")
    draw.line((785, 130, 850, 818), fill="#3a9af5", width=26)
    draw.text((120, 170), road, fill="#1b2b44")
    draw.text((1168, 240), venue, fill="#8d1d1d")
    draw.text((1070, 760), coords, fill="#102742")
    draw.text((90, 770), hint_url, fill="#20344f")
    draw.text((90, 806), timestamp_label, fill="#20344f")
    image.save(output)


def make_chat_export(output: Path, *, app: str, username: str, location: str, timestamp_label: str, url: str):
    image = Image.new("RGB", CANVAS, "#e5f6ea")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, CANVAS[0], 72), fill="#075e54")
    draw.text((26, 22), f"{app} export — {username}", fill="white")
    draw.rounded_rectangle((80, 130, 1560, 300), radius=16, fill="#dcf8c6")
    draw.rounded_rectangle((120, 360, 1500, 530), radius=16, fill="#ffffff")
    draw.text((118, 165), f"@{username} pinned location: {location}", fill="#102742")
    draw.text((118, 205), timestamp_label, fill="#24405f")
    draw.text((118, 245), url, fill="#1d69c8")
    draw.text((150, 398), "Shared from desktop capture • route overview • preserve original media", fill="#102742")
    draw.text((150, 438), "Possible witness follow-up: verify upload time and account handle", fill="#102742")
    image.save(output)


def write_manifest(base: Path) -> None:
    manifest = base / "DEMO_CORPUS_OVERVIEW.md"
    manifest.write_text(
        """
# Demo Corpus Overview

- `cairo_scene.jpg`: native EXIF + native GPS + camera-original posture.
- `giza_scene.jpg`: second native EXIF + GPS sample for timeline and map.
- `edited_scene.jpg`: exported/edited workflow sample with software tag.
- `stripped_copy.png`: metadata-stripped derivative copy.
- `Screenshot 2026-04-12 143207.png`: browser/map screenshot baseline.
- `Screenshot 2026-04-12 143207_duplicate.png`: near-duplicate compare target.
- `Screenshot 2026-04-14 120501_Map_Cairo.png`: OCR-rich map screenshot with location labels and URL clues.
- `Chat Export @bibo_fox 2026-04-14 091500.png`: OCR-rich chat/export sample with usernames, URL, and location clue.
- `IMG_20260413_170405_hidden_payload.png`: suspicious hidden payload / code-marker sample.
- `broken_animation.gif`: malformed parser-failure sample.
- `timeline_conflict_copy_2026-04-17_103000.png`: timeline-conflict sample linked to map workflow.
""".strip() + "\n",
        encoding="utf-8",
    )


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "demo_evidence"
    base.mkdir(exist_ok=True)

    now = datetime(2026, 4, 10, 10, 30)
    make_image(base / "cairo_scene.jpg", "Evidence A - Cairo", "#1f4e79", now, 30.0444, 31.2357)
    make_image(base / "giza_scene.jpg", "Evidence B - Giza", "#20435c", now + timedelta(hours=1), 29.9773, 31.1325)
    make_image(base / "edited_scene.jpg", "Evidence C - Edited", "#5f1b29", now + timedelta(hours=2), 29.9792, 31.1342, software="Adobe Photoshop")

    stripped = Image.new("RGB", (1600, 900), "#2a2f41")
    draw = ImageDraw.Draw(stripped)
    draw.text((52, 48), "Evidence D - Stripped Metadata Copy", fill="white")
    draw.text((52, 110), "Messaging export / repost workflow demo", fill="#d8f1ff")
    stripped.save(base / "stripped_copy.png")

    make_map_screenshot(
        base / "Screenshot 2026-04-12 143207.png",
        title="Google Maps - Cairo Tower - 2026-04-12 14:32:07",
        venue="Cairo Tower",
        road="26th of July Corridor",
        coords="30.0450, 31.2243",
        hint_url="https://google.com/maps/@30.0450,31.2243,15z",
        timestamp_label="Map screenshot with OCR-visible clues",
    )
    make_map_screenshot(
        base / "Screenshot 2026-04-12 143207_duplicate.png",
        title="Google Maps - Cairo Tower - 2026-04-12 14:32:07",
        venue="Cairo Tower",
        road="26th of July Corridor",
        coords="30.0450, 31.2243",
        hint_url="https://google.com/maps/@30.0450,31.2243,15z",
        timestamp_label="Map screenshot duplicate for compare mode",
    )
    make_map_screenshot(
        base / "Screenshot 2026-04-14 120501_Map_Cairo.png",
        title="Google Maps - Downtown Cairo - 2026-04-14 12:05:01",
        venue="Tahrir Square",
        road="Kasr Al Nile Bridge",
        coords="30.0444, 31.2357",
        hint_url="https://google.com/maps/@30.0444,31.2357,16z",
        timestamp_label="Possible venue lead • route overview • preserve browser history",
    )
    make_chat_export(
        base / "Chat Export @bibo_fox 2026-04-14 091500.png",
        app="WhatsApp",
        username="bibo_fox",
        location="Cairo Tower",
        timestamp_label="2026-04-14 09:15:00 • shared from Chrome desktop",
        url="https://google.com/maps/@30.0444,31.2357,16z",
    )
    make_map_screenshot(
        base / "timeline_conflict_copy_2026-04-17_103000.png",
        title="Google Maps - Cairo Tower - 2026-04-17 10:30:00",
        venue="Cairo Tower",
        road="26th of July Corridor",
        coords="30.0450, 31.2243",
        hint_url="https://google.com/maps/@30.0450,31.2243,15z",
        timestamp_label="Filename time intentionally conflicts with other evidence",
    )

    plain = Image.new("RGB", (600, 400), "#353535")
    draw = ImageDraw.Draw(plain)
    draw.text((30, 30), "Evidence E - No EXIF", fill="white")
    plain.save(base / "no_exif.png")

    dup = plain.copy()
    draw_dup = ImageDraw.Draw(dup)
    draw_dup.text((30, 80), "Duplicate of no_exif for compare mode", fill="white")
    dup.save(base / "no_exif_duplicate.png")

    hidden = base / "IMG_20260413_170405_hidden_payload.png"
    hidden.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"demo-image-data<script>alert('x')</script> token=LAUNCH-CASE-123 https://example.com/launch\n"
        + (b"A" * 160)
    )

    malformed = base / "broken_animation.gif"
    malformed.write_bytes(b"GIF89a-broken-payload")

    write_manifest(base)

    if piexif is None:
        print("Demo evidence generated without EXIF-rich samples because piexif is unavailable.")
    print(f"Demo evidence generated in: {base}")


if __name__ == "__main__":
    main()
