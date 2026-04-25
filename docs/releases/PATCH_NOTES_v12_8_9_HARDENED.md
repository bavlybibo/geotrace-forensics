# GeoTrace v12.8.8-map-intelligence — Hardened Patch Notes

## P0 hardening completed

- Prevented `chart_map.png` and `geolocation_map.html` from being copied into `redacted_text` and `courtroom_redacted` packages.
- Added strict verifier failures for sensitive visual map assets in redacted/courtroom packages.
- Aligned README version text with `APP_VERSION = 12.8.8-map-intelligence`.
- Replaced unsafe `ZipFile.extractall()` restore flow with `safe_extract_zip()` to block Zip Slip paths.

## P1 quality improvements added

- Added persistent `ocr_note` to `EvidenceRecord`.
- Displayed OCR note in report JSON/HTML and Geo/AI Guardian UI text.
- Added `map_deep` OCR mode for map-like files.
- Added OCR preprocessing variants for map screenshots: grayscale, sharpened, threshold, and high-contrast.
- Added stricter tests for:
  - no `chart_map.png` in strict packages,
  - verifier detection of strict map leaks,
  - Zip Slip restore blocking,
  - OCR note persistence,
  - filename-only map confidence cap.

## P2 product polish added

- Added `map_evidence_basis` so analysts can see whether map conclusions came from visual color signals, OCR/text, URL, dictionary, route text, or filename.
- Added `place_candidate_rankings`.
- Added Mini Case Narrator utility.
- Added agent factory with:
  - local rule agent as default,
  - optional local LLM safe fallback,
  - remote LLM blocked by default unless explicitly enabled.
- Improved PyInstaller hidden imports for reportlab, folium, matplotlib, pytesseract, pillow-heif, and PIL.

## Validation performed in this environment

- `compileall` passed for app, tests, and main.py.
- Focused new hardening tests passed: 11 passed, 1 warning.
- Additional core/report/validation smoke run reached 8 passed before the environment time limit interrupted the rest.
- Full pytest and Windows EXE build still need to be run on the Windows machine with the real venv and PyInstaller.
