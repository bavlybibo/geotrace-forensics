# GeoTrace Forensics X v12.10.7 — P0/P1 World Readiness Patch

## P0 implemented

- Added **OCR Setup Wizard** with deterministic Tesseract/language-pack checks and Windows setup hints.
- Added dashboard **Evidence Viewer** so the selected proof is visible from Mission Control, not hidden behind text panels.
- Added dashboard **Action Center** for OCR/map/privacy/export next steps.
- Added **claim-to-evidence linking** for integrity, timeline, geo/map, OCR, hidden-content, and AI-advisory claims.
- Added exportable **Claim Matrix** Markdown artifact.
- Added real **Report Builder Index** Markdown + JSON artifacts inside the export package.
- Added conservative **Timeline Confidence Model** for native metadata, filename-derived times, filesystem times, visible time strings, and single-item timeline warnings.
- Improved user-visible report artifact cards for Claim Matrix and Report Builder outputs.
- Replaced a silent visual analysis fallback with debug logging in the OSINT content reader.

## P1 scaffolding implemented

- Added **Validation Accuracy** helper for ground-truth datasets covering GPS, source type, map detection, and hidden-content detection.
- Added lightweight **Plugin Registry** for OCR, map, forensics, timeline, privacy, export, and optional local AI engines.
- Preserved the local-first model: no remote OSINT/AI calls are introduced by this patch.

## Still needs Windows validation

- Build and run the EXE on Windows.
- Run the OCR wizard against a real Tesseract install.
- Verify Manual Crop OCR with English and Arabic language packs.
- Generate a full package and inspect `claim_to_evidence_matrix_*.md`, `report_builder_index.md`, and `package_verification.txt`.
