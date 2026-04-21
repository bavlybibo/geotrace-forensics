# GeoTrace Forensics X v11.0.0-rc1

GeoTrace Forensics X is a desktop digital-forensics workspace for **image metadata extraction, timestamp recovery, GPS correlation, evidence hashing, chain-of-custody logging, duplicate clustering, comparison review, case snapshots, courtroom-aware reporting, and validation summaries**.

## What v11 adds

- Fixed the **Review-state inconsistency** so the left evidence rail, case status, and review stage stay aligned.
- Removed the old **auto page-jumping** behavior during clear/reset actions.
- Rebuilt the **preview toolbar** into grouped control rows to avoid clipped labels.
- Switched Review to a clearer **single-item review flow** with automatic first-item selection after filtering.
- Upgraded evidence cards with **risk accents, score chips, GPS/hidden markers, and timestamp confidence**.
- Added **timestamp confidence** and **GPS verification** narratives to the review workflow.
- Added **anomaly contributor** explanations and stronger courtroom-ready notes.
- Added richer **hidden/code scan summaries** with finding types and extracted indicators.
- Added stronger **report packaging** with executive summary, validation summary, and export manifest files.
- Added **validation metrics** and updated demo-evidence generation for stronger project demos.
- Expanded automated tests with **report smoke**, **validation sanity**, and a **UI-state test (skipped automatically if PyQt5 is unavailable)**.

## Supported formats

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF (via `pillow-heif`)

## How to run

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Keyboard shortcuts

- `Ctrl+N` new case
- `Ctrl+O` import files
- `Ctrl+Shift+O` import folder
- `Ctrl+R` generate reports
- `Ctrl+F` focus search
- `Ctrl+S` save notes and tags
- `Ctrl+,` open settings
- `Ctrl+Shift+C` compare mode
- `Ctrl+Shift+D` duplicate review
- `Ctrl+1..7` switch pages

## Export package contents

- HTML report
- PDF report
- CSV evidence summary
- JSON evidence summary
- Courtroom summary
- Executive summary
- Validation summary
- Export manifest JSON

## Packaging a Windows executable

Packaging files are included, but the executable is **not prebuilt inside this artifact**.

```powershell
py -m pip install pyinstaller
build_windows_exe.bat
```

## Validation status

The current artifact passes the included automated tests in this environment.
