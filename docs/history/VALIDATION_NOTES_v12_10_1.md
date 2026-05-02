# GeoTrace v12.10.1 Validation Notes

## Scope

Hardening release focused on:
- Silent failure removal in EXIF/OCR/visual/anomaly paths.
- Map Intelligence v5: offline seed geocoder, label clustering, route endpoint extraction, confidence radius, and source comparison.
- Optional local image embedding/search fallback and offline scene classification.
- CTF Answer Solver Mode with question parsing, flag formatting, alternatives, and confidence timeline.
- Manual Crop OCR preview dialog.
- CI/CD release gate, lock file, installer template, and analyst guide.

## Required Windows validation commands

```powershell
python -m compileall -q app tests main.py
python -m pytest -q
make_release.bat
dist\GeoTraceForensicsX\GeoTraceForensicsX.exe
```

## Manual smoke test

- Import GPS original.
- Import map screenshot.
- Run Deep Map OCR.
- Draw a Manual Crop OCR rectangle around map labels.
- Confirm CTF Answer Solver formats a sample flag.
- Export a redacted report package.
- Run package verifier and compare SHA256SUMS.
