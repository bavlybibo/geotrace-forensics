# GeoTrace Forensics X v12.8.10-ai-code-refactor Patch Notes

This patch focuses on code cleanliness, safer export posture, and a more explainable local AI layer.

## Code / Architecture

- Removed runtime/build/cache artifacts from the release tree.
- Unified the release version/channel to `12.8.9-public-rc1` in config and public docs.
- Added `pyproject.toml` with Ruff/Pytest configuration.
- Added local diagnostic logging helper at `app/core/logging_config.py`.
- Added split-package namespaces for future refactors:
  - `app/core/exif/`
  - `app/core/cases/`
  - `app/core/reports/`
  - `app/ui/controllers/`
- Moved workspace navigation metadata into `app/ui/controllers/navigation.py` so `main_window.py` is less hard-coded.
- Added first-phase `GeoProfile`, `OCRProfile`, and `AIProfile` facades while preserving all legacy `EvidenceRecord` fields for compatibility.

## AI Guardian / Local AI

- Added a unified Confidence Engine in `app/core/ai/confidence.py`.
- Added Evidence Strength classification in `app/core/ai/evidence_strength.py`:
  - `proof`
  - `strong_indicator`
  - `lead`
  - `weak_signal`
  - `no_signal`
- Added Privacy Guardian pre-export auditing in `app/core/ai/privacy_guardian.py`.
- Upgraded AI findings with evidence-strength score, reasons, limitations, and confidence basis.
- Enhanced Case Narrator with proof/lead counts and strongest-item reasoning.
- Enhanced AI Guardian UI with an Evidence Strength / Next Actions card.

## Map Intelligence v2

- Map Intelligence now includes:
  - evidence strength
  - limitations
  - recommended actions
  - more conservative wording around OCR/map-derived locations
- Map and OCR-derived locations are explicitly treated as investigative leads unless supported by native GPS or independent corroboration.

## OCR Modes / Cache

- Added `app/core/ocr_modes.py` with normalized modes and a stable cache-key object.
- OCR cache writes now use atomic temp-file replacement.
- Supported modes remain: `off`, `quick`, `deep`, `map_deep`.

## Reporting

- Added `privacy_guardian_<mode>.txt` as a pre-export artifact in every report package.
- JSON reports now include AI evidence strength and Map Intelligence v2 limitations/actions.

## Validation

- Added tests for profiles, confidence, evidence strength, map lead classification, and OCR cache key behavior.
- Syntax validation passed for all Python files in this patched tree.

## Notes

Full pytest and Windows EXE build were not completed in this Linux container because the available Python environment hangs during normal site initialization and Windows packaging must be validated on Windows.
