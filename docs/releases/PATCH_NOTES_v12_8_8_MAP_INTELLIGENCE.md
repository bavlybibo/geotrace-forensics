# GeoTrace Forensics X v12.8.8 — Map Intelligence Cleanup Build

## Focus
- Clean release layout and remove obsolete patch/scratch notes from the distributable zip.
- Harden the core OCR/Tesseract integration without making OCR a hard startup dependency.
- Add deeper local OSINT map intelligence for screenshots: Google Maps-style UI signals, route overlays, candidate city/area, landmarks, and confidence notes.

## Core changes
- Added `app/core/ocr_runtime.py` for resolving Tesseract from PATH, `GEOTRACE_TESSERACT_CMD`, or common Windows install paths.
- Added `app/core/map_intelligence.py` with deterministic map/route/place analysis.
- Extended `EvidenceRecord` with map intelligence fields.
- Improved AI Guardian narrative and reports to include map findings.
- Refined Geo page into a clearer Map Intelligence panel.

## Safety posture
- OCR remains optional; if Tesseract is missing, the app falls back to visual map/route analysis.
- Place/city extraction is conservative and avoids making location claims without OCR/entity evidence.
- Redacted exports continue to suppress location text and report assets.
