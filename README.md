# GeoTrace Forensics X v12.10.31


## Quick fix for Optional Stack warnings

If System Health says `Application ready: YES` but optional dependencies are missing, the app is not broken. Install the recommended optional stack first:

```bat
setup_recommended_stack_windows.bat
```

Then add GeoNames data to `data\geo\raw` and build the offline index:

```bat
import_project_geo_data.bat
```

Use `setup_ai_stack_windows.bat` only after the recommended stack is clean. AI-heavy packages are intentionally separate because they are large and not required for normal forensic/geo analysis.

For a readable diagnosis:

```bat
.venv\Scripts\python.exe tools\stack_doctor.py
```

**Local-first forensic image triage, metadata review, OCR/map clue extraction, digital-risk scoring, and court-aware reporting.**

GeoTrace helps analysts import image evidence, preserve hashes, extract metadata/OCR/map clues, separate native GPS from derived location leads, review AI Guardian cards, preview reports, and export a verifiable evidence package.

> GeoTrace does not claim to identify every location from every image. Native GPS is treated as stronger evidence. OCR/map-derived coordinates and place labels are investigative leads until independently corroborated.

---

## What changed in v12.10.24

## Release hardening added after local vision/map AI lock

- `VERSION` is now the single release identity checked by `tools/audit_release.py`, tests, and `make_release.bat`.
- Runtime folders are centralized in `app/core/runtime_paths.py` so startup, System Health, and tests agree.
- Optional Local Vision runners now have a policy gate for shell-control tokens, bounded output handling, runner SHA256 reporting, and a self-test hook.
- `tools/clean_release_artifacts.py` removes generated Python caches before packaging.


### Local Vision + Map Screenshot Mode + Calibrated Image AI

- Added an honest **Local Vision** integration path: a real offline command runner schema, manifest example, runner template, and UI/System Health status for captioning, object detection, landmark candidates, map screenshot classification, and CLIP-like similarity.
- Added **Internal Map Preview** inside Map Workspace. It renders Native GPS and Derived Geo Anchors locally as an SVG preview with confidence circles before any external provider is opened.
- Added **Geo Confidence Ladder** so every item is classified as Native GPS, Derived Geo Anchor, Map Search Lead, Map Screenshot Mode, or No Geo Anchor. This prevents derived coordinates from being mislabeled as GPS.
- Added **Map Screenshot Mode OCR zones** for search bars, route cards, pin/context-menu bubbles, labels, corners, and route polylines.
- Added compact **Map Evidence Graph** cards: Native GPS → Derived Geo → Provider Bridge → Local Vision → final posture.
- Tightened Image Threat AI calibration so **CRITICAL/100%** requires stronger multi-sensor corroboration. Privacy-only/location-only images now stay separate from technical danger.
- Added four explicit risk dimensions in Image AI payloads/UI: Technical Threat, Privacy Exposure, Geo Sensitivity, and Manipulation Suspicion.
- Added a labelled validation dataset layout and v12.10.24 ground-truth JSON template for real accuracy reporting instead of demo-only claims.
- Added targeted tests for map workspace preview/ladder/OCR zones and Image AI overconfidence calibration.

---

## What changed in v12.10.24

### GPS Repair + Privacy-Gated Real Map Bridge

- Fixed GPS normalization for more EXIF formats, including Pillow rational values, exifread ratios, tuple ratios, and string ratios, so native GPS is less likely to appear as missing when it exists.
- Added a **Map Provider Bridge** that automatically builds Google Maps, OpenStreetMap, and Apple Maps verification links from native GPS, derived map/OCR coordinates, parsed map URLs, or strong place labels.
- Expanded map URL/coordinate parsing for OpenStreetMap `mlat/mlon`, `#map=zoom/lat/lon`, Google `!3d/!4d`, route origin/destination params, plain `lat/lon` labels, and Arabic coordinate labels.
- Added privacy-gated online geocoding support through `GEOTRACE_ONLINE_MAP_LOOKUP=1`; it is **off by default** and evidence files are never uploaded automatically.
- Upgraded Map Workspace with External Map Bridge, Provider Verification Links, and a one-click **Open Provider Link** action after analyst privacy approval.
- Changed the dashboard GPS metric into **Geo Anchors** so native GPS and map/OCR-derived anchors are visible separately.
- Added focused tests for GPS ratio parsing, OSM/labelled coordinate parsing, and provider-link generation.

---

## What changed in v12.10.22

### System Health + P2 Clean Guard

- Added a dedicated **System Health** workspace page for release readiness, dependency checks, security hygiene review, P2 readiness, and truthful AI/validation status.
- Added in-app **Dependency Check** for Python modules, optional OCR/PyInstaller tooling, Tesseract presence, local vision configuration, runtime folders, OCR mode, and log privacy.
- Added **First Run Setup Wizard** to create runtime folders and apply safe defaults: bounded OCR, redacted logs, and disabled optional local AI until explicitly configured.
- Added `app/core/dependency_check.py` and `app/core/system_health.py` so readiness logic is testable outside the UI.
- Added local **visual similarity search** CLI: `python tools\visual_similarity_search.py query.jpg evidence_folder --threshold 82`.
- Expanded offline landmark/geocoder seed data and connected `data/osint/local_geocoder_places.json` into the offline geocoder.
- Added `data/validation_ground_truth.real_template.json` for real labelled validation instead of demo-only accuracy claims.
- Kept local vision honest: GeoTrace has a safe offline adapter; real AI inference requires a configured local runner through `GEOTRACE_LOCAL_VISION_COMMAND`.
- Added smoke tests for System Health/P2 assets and visual similarity tooling.

- Cleaned the main UI density across Dashboard, Review, Reports, and Metadata so raw dumps stay collapsed until requested.
- Fixed stylesheet hygiene by removing accidental literal quote tokens and adding a unified premium navigation/action style layer.
- Added `pytest.ini` so tests run from the project root without manual `PYTHONPATH` setup.
- Tightened release hygiene by removing generated `__pycache__` / pytest cache folders from the packaged tree.
- Shortened repeated dashboard narratives and priority text to make decisions clearer.
- Added missing release files: `requirements.txt`, `requirements-dev.txt`, `main.py`, Windows setup/run/release scripts, and PyInstaller `.spec` files.
- Upgraded Image Threat AI with sensor-fusion scoring, weighted contributors, threat family, and decision lane.
- Improved false-positive controls so GPS/map/visible-text privacy issues do not become fake “malware” calls.
- Added AI Guardian visual refresh: new AI hero palette, semantic Image AI metric, and clearer danger/review/safe card colors.
- Extended reports with Image AI lane/family/sensor/contributor fields.
- Added calibrated Image AI triage: evidence grade, P0/P1/P2/P3 priority, HOT/WARM/COOL temperature, missing-evidence notes, safe-handling profile, and export policy.
- Added an Image AI Triage Queue panel inside AI Guardian so analysts see the practical handling decision immediately.
- Expanded privacy/exposure detection for identity-document, financial, government-ID, QR/barcode, OTP, and recovery-code clues without falsely labeling them as malware.
- Aligned product version to `12.10.22` in source and documentation.
- Added release audit tooling: `python tools\audit_release.py`.
- Added smoke tests for release files, package signatures, report preview, and map false-positive guards.
- Added bounded OCR defaults: per-call timeout, max OCR calls, and global OCR budget.
- Strengthened map/place filtering so generic OCR noise like `exif`, `image`, `metadata`, and demo filenames do not become location candidates.
- Added validation/benchmark seed files for accuracy reporting.

---

## Install on Windows

```bat
setup_windows.bat
```

This creates `.venv`, upgrades pip, installs runtime/developer dependencies, and runs a compile sanity check.

## Run

```bat
run_windows.bat
```

Manual alternative:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe main.py
```

## Build release

```bat
make_release.bat
```

The release script cleans caches, compiles the app, runs audit checks, runs pytest, builds the EXE, creates a release ZIP, and writes SHA256 sums.

## Manual release gate

```bat
python tools\audit_release.py
python -m compileall -q app tests main.py
python -m pytest -q
pyinstaller --noconfirm --clean geotrace_forensics_x.spec
```

---

## Runtime controls

You can tune OCR and privacy from the app settings or through environment variables before launch:

```bat
set GEOTRACE_OCR_MODE=quick
set GEOTRACE_OCR_TIMEOUT=0.8
set GEOTRACE_OCR_GLOBAL_TIMEOUT=5.0
set GEOTRACE_OCR_MAX_CALLS=4
set GEOTRACE_LOG_PRIVACY=redacted
set GEOTRACE_PACKAGE_SIGNING_KEY=change-this-local-secret
set GEOTRACE_PACKAGE_SIGNING_KEY_ID=lab-key-01
```

OCR modes: `off`, `quick`, `deep`, `map_deep`.

---

## Core workflow

```text
Import evidence
  ↓
Preserve hashes + working copy
  ↓
Parse metadata / EXIF / container signals
  ↓
Run bounded OCR + map clue extraction when useful
  ↓
Classify native GPS vs derived geo leads
  ↓
Review AI Guardian and Digital Risk cards
  ↓
Preview report package
  ↓
Export + verify package signature/manifest
```

---

## Workspace modes

| Mode | Best for | Pages shown |
|---|---|---|
| Executive | Demo, management review, high-level readiness | Dashboard, Reports, Cases |
| Analyst | Normal investigation workflow | Dashboard, Review, Geo, Map Workspace, Timeline, Custody, Reports, Cases, AI Guardian |
| Technical | Deep parser/OCR/OSINT/validation review | All pages including OSINT Workbench |

---

## Key capabilities

- Evidence intake, isolated case storage, source/working-copy hashing, and custody timeline.
- EXIF/container parsing, GPS extraction, timestamp classification, hidden-content heuristics, and pixel/stego indicators.
- OCR diagnostics, manual crop OCR workflow, map URL/coordinate parsing, route/map context, and offline landmark seed support.
- AI Guardian cards, digital-risk verdicts, contradiction notes, evidence basis, and next actions.
- Report preview, HTML/PDF/CSV/JSON exports, executive summary, courtroom notes, OSINT appendix, claim matrix, validation template, and package verification.
- Optional HMAC package signing using `GEOTRACE_PACKAGE_SIGNING_KEY`.

---

## Validation and benchmark workflow

1. Build or import a known validation dataset.
2. Copy `data/validation_ground_truth.sample.json` and replace sample filenames/checks with real expected outcomes.
3. Analyze the dataset in GeoTrace.
4. Export JSON records.
5. Run:

```bat
python tools\benchmark_accuracy.py exports\records.json data\validation_ground_truth.sample.json
```

Use this to prove false-positive reduction and extraction accuracy over time.

---

## Release hygiene

Do not publish source packages containing:

- `__pycache__/`
- `*.pyc`
- local `.venv/`
- private case data
- unredacted evidence exports

Run:

```bat
python tools\audit_release.py
```

before GitHub upload or external delivery.

---

## Safety and limitations

GeoTrace is a triage and reporting assistant, not an automatic legal conclusion engine. Analysts must verify sensitive claims, especially derived geolocation, OCR text, hidden content, and source attribution, with independent evidence before final reporting.

## Image Threat AI hardening

This branch includes a focused Image Threat AI layer for deciding whether an imported image is technically dangerous or only privacy/context-sensitive.

The judgement appears in AI Guardian, record details, JSON exports, and HTML reports as:

- `SAFE` — no technical danger evidence.
- `LOW` — weak or privacy-only signal.
- `MEDIUM` — review required, but not confirmed dangerous.
- `HIGH` — strong technical image-risk indicators.
- `CRITICAL` — isolate immediately and validate carved/decoded artifacts.

The engine separates visible OCR from hidden payload evidence. For example, code visible inside a screenshot is not treated as an injected payload unless container, parser, or pixel-level evidence corroborates it.

Run the new checks with:

```bat
python -m pytest tests\test_image_threat_ai.py -q
```

### v12.10.26 Geo Import Ready Patch

- `tools/build_offline_geocoder_index.py` now imports processed GeoNames JSON such as `data/geo/processed/places_geonames.json`.
- Accepts JSON arrays, `{ "places": [...] }`, GeoJSON, JSONL/NDJSON, CSV/TSV, and GeoNames TXT.
- Normalizes `country_code`, `name_ascii`, list-based aliases, and source labels into `data/osint/generated_geocoder_index.json`.

### v12.10.25 Geo Data & Offline Geocoder Upgrade

- Added Arabic/English country/city normalization via `data/osint/geo_aliases.json`.
- Expanded the offline geocoder seed with more MENA, Europe, and global city/POI coverage.
- Added conservative fuzzy matching for OCR misspellings without upgrading text-only hits to GPS evidence.
- Added `tools/build_offline_geocoder_index.py` to import larger local datasets from GeoNames/Natural Earth/Wikidata-style CSV exports.
- Added `docs/GEO_DATA_SOURCES.md` with source policy, privacy rules, and scaling workflow.

## Project-contained GeoNames / POI data

To keep your large geo database inside the project, place your processed file here:

```text
data/geo/processed/places_geonames.json
```

Then run:

```powershell
python tools\build_offline_geocoder_index.py
```

Or double-click:

```text
import_project_geo_data.bat
```

GeoTrace generates and reads this runtime index automatically:

```text
data/osint/generated_geocoder_index.json
```

All matches from this database are treated as **Derived Location Leads**, not Native GPS.

Release version: v12.10.29



## v12.10.29 Clean Optional Stack + GeoNames Enrichment workflow

This release separates the stack into clean requirement groups:

```text
requirements.txt          core app runtime
requirements-ui.txt       QtAwesome + PyQtGraph UI polish
requirements-geo.txt      RapidFuzz + geopy + shapely + H3 geo intelligence
requirements-ai.txt       heavy local AI/vision stack
requirements-osint.txt    privacy-gated online OSINT helpers
requirements-all.txt      full stack
```

Recommended setup:

```powershell
setup_windows.bat
```

Full AI setup:

```powershell
setup_full_stack_windows.bat
```

For the large city database, place one file before running the importer:

```text
data/geo/raw/cities1000/cities15000.txt
```

or:

```text
data/geo/raw/cities1000/cities15000.zip
```

Then run:

```powershell
import_project_geo_data.bat
```

The generated file is:

```text
data/osint/generated_geocoder_index.json
```

All GeoNames/OSINT matches remain **Derived Location Leads**, not native GPS.


## v12.10.29 GeoData placement

Recommended project-local data layout:

```text
data/geo/raw/
  cities1000.zip              # recommended wide city coverage
  alternateNamesV2.zip        # recommended Arabic/English aliases
  countryInfo.txt             # optional country names/ISO metadata
  admin1CodesASCII.txt        # optional governorate/state names
  admin2Codes.txt             # optional district/county names
  timeZones.txt               # optional timezone metadata
```

Then run:

```bat
import_project_geo_data.bat
```

The importer now accepts `cities1000`, `cities5000`, `cities15000`, `allCountries`, processed JSON/GeoJSON/CSV, and optional GeoNames helper files. It writes:

```text
data/osint/generated_geocoder_index.json
```

Evidence rule: every result from this index is a **derived location lead**, not native GPS proof.


## Optional Forensics + Heavy AI Stack

For deeper forensic/geo/vision capability without breaking the base app:

```bat
setup_forensics_stack_windows.bat
```

This installs `requirements-forensics.txt` for ExifTool bridge support, QR/barcode
detection, ImageHash, timezonefinder, pycountry, and DuckDB.

Heavy local AI remains separate:

```bat
pip install -r requirements-ai-heavy.txt
set GEOTRACE_YOLO_ENABLED=1
set GEOTRACE_YOLO_MODEL=C:\path\to\yolov8n.pt
```

YOLO/PaddleOCR are optional and not required for normal startup. See
`docs/OPTIONAL_FORENSICS_AI_STACK.md`.
