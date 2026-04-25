# GeoTrace Forensics X v12.8.15 — Codebase Cleanup + OSINT Workbench RC1

## Release identity
- Bumped the working release to `12.8.15-codebase-osint-workbench-rc1`.
- Kept the build channel stable as `Public Release Candidate`.
- Updated release packaging names so Windows packages no longer inherit older v12.8.8/v12.8.14 labels.

## Codebase cleanup
- Started the safe refactor path without rewriting high-risk core files in one step.
- Moved deterministic visual map scoring into `app/core/vision/map_visuals.py`.
- Added map/location evidence-strength policy in `app/core/map/evidence.py`.
- Kept backwards-compatible wrappers in `map_intelligence.py` so existing tests and imports keep working.

## OSINT Workbench
- Added a usable next-scan profile control for region and OCR mode.
- Added profile status text explaining that existing records are not reprocessed until rescanned/imported.
- Kept analyst actions: verify top lead, reject top lead, and reset to review.

## Reports
- Added a dedicated OSINT appendix export.
- Added OSINT appendix to the timestamped report package payload.
- Added an OSINT Appendix artifact card in the Reports page.
- OSINT appendix preserves the investigation distinction between `proof`, `lead`, and `weak_signal`.

## Safety posture
- Visual map signals remain conservative and cannot become proof without stronger corroboration.
- Shareable/Courtroom export modes continue to redact sensitive location pivots through the ReportService redaction callbacks.
