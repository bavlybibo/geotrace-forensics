# GeoTrace v12.10.9 Validation Notes

## Scope
- Adds a conservative Launch Readiness Gate for dashboard/report handoff.
- Adds validation ground-truth template generation to every export package.
- Refreshes explainability/claim rows at report time so older saved cases do not leak stale placeholder text.
- Enables map exports for derived map/coordinate evidence, not only native GPS evidence.

## Manual Windows checks still required
- `setup_windows.bat`
- `pytest`
- `build_windows_exe.bat`
- Run the generated EXE from `dist/`.
- Import a map screenshot and confirm the Report Builder Index includes the Launch Readiness Gate.
