# GeoTrace v12.9.7 — Deep Image AI & Pixel Stego Hardening

## What changed

- Added `app/core/vision/image_intelligence.py` for offline deep image-detail triage.
- Expanded `app/core/vision/pixel_stego.py` to scan isolated channel LSB plus packed RGB/BGR/RGBA bitstreams and second-lowest bit-plane patterns.
- Added even/odd pair-balance, row-bias, composite-stream metrics, and stronger analyst-facing limitations.
- Connected image detail fields to `EvidenceRecord`, OSINT Content Reader, AI Guardian, OSINT Workbench, CTF methodology, JSON export, and HTML reports.

## Analyst model

The new logic separates proof from leads:

- Hard anchors: native GPS, visible coordinates, map/share URLs.
- Strong leads: OCR labels, known landmarks, independent source families.
- Triage-only: visual cues, image-detail object hints, pixel anomalies without decoded payload.

## Validation notes

- Syntax was checked with AST parsing for modified Python files in this environment.
- Full UI execution still requires a Windows/PyQt environment with project dependencies installed.
- Run `python -m pytest -q` on the release machine after installing requirements.
