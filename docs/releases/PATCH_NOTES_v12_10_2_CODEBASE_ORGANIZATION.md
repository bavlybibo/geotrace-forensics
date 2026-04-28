# Patch Notes — v12.10.2 Codebase Organization

## Scope

Organization-only build. No new detection feature was intentionally added.

## Changes

- Added compatibility facades for legacy import paths.
- Moved large root-level core modules into clearer packages.
- Moved CTF UI page into a dedicated `pages.ctf` package.
- Moved the main window implementation into `ui.window`.
- Preserved old imports for `CaseManager`, `ReportService`, EXIF helpers,
  anomaly helpers, visual clue helpers, map intelligence helpers, and CTF page
  builders.
- Added codebase organization notes for future refactoring.

## Validation target

Run:

```powershell
python -m compileall -q app tests main.py
python -m pytest -q
make_release.bat
```
