# GeoTrace Forensics X v12.8.14 — Release Cleanup + OSINT Workbench Preview

## Fixed

- Unified release identity across `app/config.py`, `README.md`, `pyproject.toml`, and `make_release.bat`.
- Restored `APP_BUILD_CHANNEL = "Public Release Candidate"` to satisfy release readiness tests.
- Hardened `make_release.bat` cleanup for build/cache/temp artifacts.
- Fixed OCR-off behavior so `GEOTRACE_OCR_MODE=off` cannot be bypassed by forced OCR calls.
- Added `setHtml()` auto-height support and scrollbar fallback for AI Guardian HTML cards.
- Made case backup restore rollback-safe at the filesystem layer.
- Reconnected structured OSINT cache loading during case snapshot reload.

## Added

- OSINT Workbench preview page with:
  - Hypothesis cards.
  - Top-lead verify/reject/reset buttons.
  - Entity graph preview.
  - Evidence strength summary.
  - OCR + region profile summary.
  - Privacy review and export appendix preview.
- Registry-style migration ledger in `app/core/migrations.py`.
- `app/core/vision/` helper module for visual map-signal wording.
- `app/core/map/` helper module for conservative map evidence-strength wording.

## Notes

Full architectural splitting of `report_service.py`, `case_manager.py`, and `visual_clues.py` is intentionally deferred to the next cleanup release because those files are high-risk and already covered by existing tests. This release focuses on safe blocker fixes plus a v12.9 OSINT Workbench preview.
