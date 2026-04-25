# GeoTrace Forensics X v12.8.16 — Report + OSINT Polish RC1

This release polishes the v12.8.15 launch-candidate run based on real UI screenshots and generated report packages.

## Fixed

- Fixed PDF Evidence Matrix text overlap by wrapping table cells with ReportLab Paragraphs and tighter table styles.
- Fixed OCR wording inconsistency when OCR is attempted but returns no stable text.
- Added a weak-signal OSINT hypothesis card for visual map/navigation screenshots even when no stable place label is recovered.
- Improved OSINT Workbench profile display so selected controls and active next-scan profile are shown separately.
- Updated version identity to `12.8.16-report-osint-polish-rc1` across app config, README, pyproject, and release script.

## Notes

- Visual map detections still remain `weak_signal` unless corroborated by OCR labels, map URLs, native GPS, or source-app history.
- Internal Full exports may include raw paths/previews and should not be shared externally without generating a redacted package.
