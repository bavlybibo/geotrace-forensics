# GeoTrace Forensics X v12.2.0-polish

GeoTrace Forensics X is a desktop digital-forensics workspace for **image metadata extraction, timestamp recovery, GPS correlation, evidence hashing, case isolation, duplicate clustering, review workflows, courtroom-aware reporting, and chain-of-custody logging**.

This polish build focuses on **cleaner review UX**, **state consistency**, **stronger presentation quality**, **leaner project structure**, and **report previews with screenshots**.

## What changed in this hardening pass

- Replaced the misleading default integrity state with **derived integrity states**:
  - `Verified`
  - `Partial`
  - `Review Required`
  - `Pending Review`
- Removed the old behavior that could make a case look fully "Verified" before real checks were applied.
- Added **integrity notes** per evidence item so the analyst can explain *why* an item is verified, partial, or review-required.
- Hardened EXIF handling:
  - If `exifread` is unavailable, the app now surfaces an **explicit warning** instead of silently acting like the file simply has no EXIF.
  - EXIF parser failures now produce a visible analyst-facing note.
- Hardened filesystem time handling:
  - The app no longer treats Unix/Linux `ctime` as a true creation time.
  - Birth/creation time is shown only when the platform exposes it reliably.
  - A **birth-time note** is stored per record to explain platform limitations.
- Improved duplicate detection by grouping **near-matching perceptual hashes**, not just exact hash equality.
- Reduced false-positive pressure in hidden-content analysis:
  - Plain readable strings are preserved for **context only**.
  - Only stronger code-like markers are counted as **hidden/code hits**.
- Added a **hash-chained custody log** with `prev_hash` and `event_hash` so the case audit trail becomes tamper-evident within the app workflow.
- Added custody-chain validation summaries to reports and case validation strings.
- Tightened UI wording:
  - `Analysis complete` → `Analysis finished`
  - `Hidden / Code` tab → `Hidden Scan`
  - integrity header now shows **Checked** instead of implying automatic full verification.
- Added new automated tests for:
  - near-duplicate grouping,
  - filesystem time-note behavior,
  - updated integrity/validation summaries.

## Supported formats

Common investigation image formats supported in this build:

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF (via `pillow-heif`)

## Run

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Investigation workflow

1. Create or switch to an isolated case.
2. Import files or a folder.
3. Let the workspace:
   - compute SHA-256 / MD5,
   - extract metadata,
   - recover timestamps,
   - decode GPS when available,
   - inspect structure/signature,
   - run hidden-content heuristics,
   - cluster near-duplicates,
   - write custody events.
4. Review the item in the **Review** page.
5. Use the **Hidden Scan**, **Metadata**, **Audit**, **Timeline**, and **Compare** flows to corroborate findings.
6. Export the HTML / PDF / JSON / CSV / courtroom package.

## Validation semantics

The tool intentionally separates **structural validation** from **provenance certainty**.

- `Verified` = parser + signature + hashing checks completed cleanly for this container.
- `Partial` = the file rendered, but one or more checks are limited (for example, EXIF engine unavailable or weak/header-only trust).
- `Review Required` = parser/signature problems require analyst confirmation.
- `Pending Review` = analysis has not finished yet.

This means `Verified` does **not** automatically prove origin, authenticity, or legal admissibility by itself. It means the file container passed the current structural checks.

## Hidden-content semantics

The hidden-content workflow is heuristic by design.

- **Code-like indicators** are treated as higher-priority findings.
- **Readable strings** without code markers are kept for analyst context only.
- The app avoids counting plain readable strings as hidden-code hits.

## Chain of custody

The case audit trail now includes a simple hash chain:

- each event stores `prev_hash`
- each event stores its own `event_hash`
- the app can validate the chain and report whether it is intact

This is stronger than a plain SQLite event log, but it is still an educational / project-grade control rather than a full external immutable ledger.

## Project mapping to course requirements

This build directly supports the core items expected for the **Image Metadata & Geolocation** project:

- EXIF extraction
- GPS decoding
- timeline usage
- anomaly / manipulation indicators
- forensic reporting
- evidence chain / custody logging

The original project brief asks for tool functionality, investigation accuracy, documentation, validation, and evidence-chain handling. This build is aligned to that scope.

## Keyboard shortcuts

- `Ctrl+N` new case
- `Ctrl+O` import files
- `Ctrl+Shift+O` import folder
- `Ctrl+R` generate reports
- `Ctrl+F` focus search
- `Ctrl+S` save notes
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

## Test status

The current hardened artifact passes the included automated tests in this environment.


## V12 image reasoning upgrades
- Derived geo clues from visible map/browser content
- OCR-based visible text extraction for screenshots
- Time candidate engine with conflict tracking
- Environment/app detection for screenshots and browser captures
- Tiered hidden-content scan with structural payload warnings


## Windows setup notes

- `run_windows.bat` and `setup_windows.bat` now create a project-local `.temp` folder and force `TEMP` / `TMP` to use it. This avoids the Windows error `No usable temporary directory found` that can break `venv` or `pip`.
- OCR is optional. `pytesseract` can be installed from `requirements.txt`, but full OCR support also needs the external Tesseract OCR application available on the system PATH. If Tesseract is missing, the app still runs and simply reports that OCR is unavailable.
- `tools/generate_demo_evidence.py` now degrades gracefully if `piexif` is missing; it will still generate demo images, but EXIF-rich samples will be weaker.

### If Windows still shows a TEMP/TMP error

Run `fix_windows_temp.bat`, open a **new** terminal, then run `setup_windows.bat` again.
