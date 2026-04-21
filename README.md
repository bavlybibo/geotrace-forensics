# GeoTrace Forensics X v5

**GeoTrace Forensics X** is a polished desktop digital-forensics tool built for investigators, students, and analysts who need fast, structured insight from image-based evidence.

It focuses on **image metadata extraction, timestamp recovery, GPS correlation, evidence hashing, chain-of-custody logging, duplicate detection, and analyst-ready reporting** in a clean cyber-style interface.

---

## Overview

GeoTrace Forensics X helps analysts examine image evidence through a practical forensic workflow:

**Acquire → Verify → Extract → Correlate → Score → Report**

The tool is designed to support real investigative work by turning raw image files into structured forensic findings, visual insights, and presentation-ready reports.

---

## Key Capabilities

### Metadata Extraction
GeoTrace extracts a broad range of metadata and forensic context, including:

- EXIF camera and device tags
- software / editor tags
- lens, ISO, exposure, focal length
- image format, DPI, color mode, alpha channel
- filesystem timestamps
- filename-based timestamp recovery
- GPS coordinates and altitude when available

### Timestamp Recovery
The tool does not rely only on EXIF. It also attempts to recover time context from:

- EXIF date/time fields
- filename patterns
- filesystem timestamps
- exported-media naming conventions

This is especially useful for screenshots, messaging exports, and edited media where full EXIF is often missing.

### GPS Correlation
When GPS data is present, GeoTrace helps correlate:

- latitude / longitude
- altitude
- location consistency
- geospatial investigation leads

### Evidence Integrity
To support sound forensic handling, the tool includes:

- file hashing
- evidence verification workflow
- chain-of-custody event logging

### Duplicate Detection
GeoTrace uses **perceptual hashing** to identify visually similar or near-duplicate images, not just identical files.

This helps investigators detect:

- repeated evidence
- resized or recompressed copies
- visually similar images with different file hashes

### Analyst-Focused Scoring
The tool applies **context-aware anomaly scoring** to reduce false positives, especially for:

- screenshots
- messaging exports
- edited/exported media
- synthetic or non-camera image sources

Each item is evaluated with both:

- **risk score**
- **confidence score**

This gives more realistic and explainable results.

### Reporting & Export
GeoTrace can generate a complete export package in:

- HTML
- PDF
- CSV
- JSON

It also provides operational charts for:

- source-type distribution
- risk levels
- GPS coverage
- duplicate coverage

---

## What’s New in v5

Version 5 introduces a more refined and investigation-ready experience, including:

- premium dark cyber UI
- splash screen and app icon
- richer metadata extraction
- smarter timestamp recovery
- improved anomaly scoring logic
- perceptual duplicate clustering
- interactive Geo / OSINT leads panel
- multi-format export package
- analytical charts for reporting and presentation

---

## Supported Formats

GeoTrace currently supports:

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF *(via `pillow-heif`)*

---

## Quick Start

### Windows

Install dependencies and run the application:

```powershell
python -m pip install -r requirements.txt
python main.py