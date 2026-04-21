# GeoTrace Forensics X v10.1.1-rc1

GeoTrace Forensics X is a desktop digital-forensics workspace for **image metadata extraction, timestamp recovery, GPS correlation, evidence hashing, chain-of-custody logging, duplicate clustering, comparison review, case snapshots, and analyst-ready reporting**.

## What this release adds

- First-run **onboarding flow** with shortcuts to demo data, import, or the Cases page
- Persistent **settings panel** powered by `QSettings`
- Stronger **case save / load / reopen** using per-case JSON snapshots and a dedicated Cases page
- Better **search / filter / sort / bookmark** controls inside the Review page
- Global **keyboard shortcuts** for common forensic actions
- Report **branding, versioning, methodology, limits, and footer identity**
- **Export validation** with completion toasts and package notes
- User-visible **graceful error logs** mirrored to `logs/app_errors.log`
- Window-level **drag & drop** intake for files and folders
- **Batch queue** support so later imports can wait behind the active analysis
- **Recent cases** dialog plus a full Cases page
- **Evidence compare mode** for side-by-side review
- **Duplicate cluster review workflow** with jump-to-item navigation
- Stronger **timeline narrative generation**
- Improved **map intelligence** and GPS reasoning states
- **Analyst note templates** for triage, timeline, courtroom, OSINT, and duplicate workflows
- Better **audit trail viewer** with filtering and copy support
- Windows **packaging scaffolding** for PyInstaller-based executable builds

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

## Packaging a Windows executable

Packaging files are included, but the executable is **not prebuilt inside this artifact**.

```powershell
py -m pip install pyinstaller
build_windows_exe.bat
```

## Validation status

Core automated tests pass in this release.
