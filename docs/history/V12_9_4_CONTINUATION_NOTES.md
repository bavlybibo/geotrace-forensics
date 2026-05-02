# GeoTrace v12.9.4 — Continuation Hardening Notes

## What changed

- Version identity bumped and aligned to `12.9.4`.
- CTF GeoLocator now includes:
  - OCR Diagnostics panel.
  - Selected Evidence Preview / Crop Plan panel.
  - Visual scene/tags from the local CTF visual clue engine.
  - Multi-zone Manual Crop OCR rather than a single fixed center crop.
- Evidence records now persist:
  - `ctf_visual_clue_profile`
  - `manual_crop_assets`
  - `ocr_diagnostics`
- Offline CTF intelligence improved with:
  - broader local landmark seed dataset,
  - expanded country/region profiles,
  - map/route/photo/UI visual clue heuristics.
- Report package integrity improved with:
  - `export_manifest.sha256` sidecar,
  - verifier check for the manifest signature sidecar.

## Still intentionally offline

GeoTrace does not upload evidence, call reverse-image search, or query online maps automatically. Online OSINT remains a manual, privacy-gated workflow.

## Required Windows release checks

```bat
python -m compileall -q app tests main.py
python -m pytest -q
build_windows_exe.bat
```

Then run the EXE from `dist` and verify:

1. Import demo evidence.
2. Open CTF GeoLocator.
3. Run Deep Map OCR.
4. Run Manual Crop OCR.
5. Generate report package.
6. Run package verifier.
