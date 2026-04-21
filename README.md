# GeoTrace Forensics X v4

# GeoTrace Forensics X

A polished desktop digital-forensics tool for **image metadata extraction, timestamp recovery, GPS correlation, evidence hashing, chain-of-custody logging, duplicate clustering, and analyst-ready reporting**.

## What this version adds

- Premium dark cyber UI with **splash screen** and app icon
- Rich metadata extraction for:
  - EXIF camera/device tags
  - software/editor tags
  - lens / ISO / exposure / focal length
  - color mode / alpha channel / DPI / format
  - timestamp recovery from EXIF, filename patterns, and filesystem timestamps
  - GPS coordinates and altitude when available
- **Context-aware anomaly scoring** to reduce false positives on screenshots and chat exports
- **Perceptual hash clustering** to spot near-duplicate images
- Interactive **Geo / OSINT leads** panel
- HTML / PDF / CSV / JSON export package
- Operational charts for source types, risks, and duplicate/GPS coverage

## Supported formats

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF (via `pillow-heif`)

## How to run on Windows

```powershell
python -m pip install -r requirements.txt
python main.py
```

Or use the batch files:

- `setup_windows.bat`
- `run_windows.bat`

## Suggested demo workflow

1. Import 1 image or a folder of evidence images
2. Review the dashboard stats
3. Open one image and show the preview + metadata intelligence tab
4. Show the timeline tab and explain timestamp recovery
5. Show the insights charts
6. Open the geolocation map if GPS is available
7. Generate the HTML/PDF/CSV/JSON report package

## Investigation methodology

This build follows a practical workflow:

**Acquire → Verify → Extract → Correlate → Score → Report**

- Acquire: load evidence image(s)
- Verify: compute hashes and log import event
- Extract: pull metadata and filesystem context
- Correlate: link timestamps, device hints, GPS, duplicates
- Score: assign anomaly/risk indicators with context
- Report: export a presentation-ready package

## Recommended presentation talking points

- Screenshots and messaging exports often lack EXIF, so the tool uses **smart fallback timestamp recovery** instead of treating every missing tag as suspicious.
- The tool distinguishes **source types** such as screenshot, messaging export, camera photo, edited/exported media, and graphic assets.
- Each item gets both a **risk score** and a **confidence score** to show analytical maturity.
- Duplicate clusters are identified using a **perceptual fingerprint**, not only raw file hashes.



## v4 upgrades
- cleaner command-center layout with larger terminals and preview panes
- footer removed to free vertical space
- deeper terminal-style metadata, geo, timeline, and custody views
- improved timestamp parsing for WhatsApp-style filenames with AM/PM
- cleaner chart rendering and scalable chart panels
