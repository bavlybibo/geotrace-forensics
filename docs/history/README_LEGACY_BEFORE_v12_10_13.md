# GeoTrace Forensics X v12.10.13 — Release Hygiene & Security Closure

> **v12.10.13 closure scope:** finalizes the working release around three UI modes, an internal Map Workspace, report preview before export, structured JSONL failure logs, validation schema compatibility, optional local vision status, custom offline landmark indexes, and optional HMAC-backed package signing. The tool remains local-first and explainable: derived map/OCR coordinates are investigative leads, not native GPS proof.

## v12.10.13 Quick Launch Notes

- Use **Executive** mode for clean demos and management review.
- Use **Analyst** mode for the normal import → review → map/OCR → report workflow.
- Use **Technical** mode when you need every parser/OCR/hidden-content/OSINT panel.
- Open **Map Workspace** before making any location claim.
- Click **Preview Export** before generating the final package.
- Check `logs/structured_failures.jsonl` when anything fails.
- Optional local-only extensions:
  - `GEOTRACE_LOCAL_VISION_MODEL` for a local vision model folder/manifest status check.
  - `GEOTRACE_LANDMARK_INDEX` for a custom offline landmark JSON.
  - `GEOTRACE_PACKAGE_SIGNING_KEY` and `GEOTRACE_PACKAGE_SIGNING_KEY_ID` for HMAC package signing.

---

# GeoTrace Forensics X v12.10.9 — Launch Gate & Evidence Handoff Hardening Patch

> **v12.10.9 scope:** adds a conservative Launch Readiness Gate, stronger export handoff warnings, validation ground-truth template generation, and report-time explainability refresh so stale fields like “No GPS issue summary generated” are replaced by useful derived-geo limitations. Previous v12.10.8 scope: continues the world-readiness track with initial-scan map-field persistence, a reusable redaction engine, package signature envelope, multi-case comparison helpers, enterprise audit summary helpers, and stronger verification hooks. Previous v12.10.6 scope: adds a Tesseract-independent visual coordinate fallback for Google Maps right-click context menus, so screenshots containing decimal coordinates like `40.48168, -3.21450` become derived coordinate anchors even when OCR fails. v12.10.5 also fixes weak map screenshot recognition, auto-escalates map-like screenshots to deep OCR, adds focused Google Maps context-menu coordinate crops, and improves global place-label extraction. Previous v12.10.4 scope strengthened the offline AI image pipeline with reasoning-strategy scores, review gates, corroboration targets, and clearer AI Guardian/report explainability. It preserves the v12.10.3 tile-attention methodology while adding OCR/map/geo/hidden-content priorities without network calls or heavyweight model inference.


## v12.10.4 AI Reasoning Strategy & Image Review Pipeline

This release adds a strategy layer on top of the deep image methodology:

- **Analysis strategy gate**: classifies each image into map-first, OCR-first, geolocation-hypothesis, hidden-content-first, metadata/context-first, or balanced visual review.
- **Priority scoring**: exposes bounded OCR, map, geolocation, hidden-content, and detail-complexity scores inside `image_detail_metrics`.
- **Quality gate**: marks images that need enhancement/cropping before final wording.
- **Corroboration target**: tells the analyst what evidence packet is required before claiming a location, OCR result, or hidden-content finding.
- **AI Guardian/report integration**: strategy, scores, gates, and corroboration targets now appear in AI Guardian, OSINT Workbench, batch AI actions, and HTML/JSON reports.
- **Performance-safe design**: still runs on thumbnails and bounded grids; no external model or network dependency was added.

## v12.10.3 Deep Image Methodology & AI Detail Upgrade

- Deep Image Intelligence now uses bounded thumbnail analysis plus a 4x4 tile grid to identify high-attention regions for manual crop/OCR review.
- Image profiles now include scene descriptors, attention region boxes, methodology steps, and performance notes for smoother analyst workflow.
- OSINT Content Reader and CTF methodology now consume deep image regions/descriptors instead of relying only on broad layout/object hints.
- AI Guardian now surfaces attention regions, scene descriptors, and methodology guidance directly in the Deep Image Intelligence cards.
- JSON/report exports include the new methodology artifacts so technical reports can explain how image details were prioritized.
- The implementation remains offline, deterministic, explainable, and performance-bounded to keep imports/rescans smooth.

## v12.10.2 Codebase Organization & Compatibility Split


### v12.10.2 organization-only hardening

This build makes Reports/Export, Privacy, CTF Answer Readiness, and Map Intelligence clearer and safer. Map screenshots now get a stronger map-type profile (route, road/tiled, dark map, satellite/terrain-like, transit-like), but the app only treats a location as answer-ready when GPS, visible coordinates, a map URL, OCR/place labels, or a verified landmark/place anchor exists. Visual-only map context remains a lead, not proof.

- Reports & Export now shows package, privacy, verification, and CTF readiness metrics.
- Internal Full exports show a stronger confirmation warning and are clearly marked as not share-safe.
- CTF Answer Engine now separates map type/context from final answer readiness.
- Map Intelligence includes answer readiness score, anchor status, visual map profile, and extraction plan.
- Map output can open an intelligence board when no coordinate is available, instead of failing silently.
- Approximate known-place plotting is labeled as approximate and never outranks native GPS or visible coordinates.

### v12.10.1 premium demo-ready interface + deep image investigation lab

This build merges the duplicated OSINT and CTF navigation into one unified investigation workspace. This revision also tightens the visual system with cleaner hero sections, KPI pills, stronger table readability, improved card hierarchy, and more professional empty-state guidance. The CTF workflow is now embedded inside the OSINT Workbench as a researcher-grade methodology lab with source hierarchy, pixel/hidden-content triage, OCR/map review, candidate validation, answer readiness, and privacy-gated pivots. External web/reverse-image workflows remain manual and privacy-gated.



### v12.10.1 UI/demo polish layer

- Dashboard is now a mission-control screen with a polished hero, workflow/readiness pills, cleaner chart cards, and less empty vertical space.
- Geo Review now has a stronger intelligence-board layout with GPS/context/place/route KPI pills and tighter explanation panels.
- Reports & Export is now a command center with package metrics, a 3-column artifact grid, clearer verification actions, and compact status/error panels.
- Shared visual language is documented in `app/ui/design_system.py` and applied through QSS selectors such as `HeroPanel`, `MetricPill`, `GeoSignalRail`, and `ReportArtifactCard`.

- Unified OSINT + CTF workspace so image-solving, hypotheses, entities, OCR/region profile, and candidate review happen in one place.
- New Hacker Methodology Matrix grades each image through intake, hidden-content triage, hard anchors, OCR/visual narrowing, candidate validation, and answer readiness.
- Deep Map OCR and Extract Map Labels now rescan selected evidence immediately.
- Manual Crop OCR can extract map/label text from a center crop and merge it into the CTF workflow.
- CTF GeoLocator writeups are included inside the generated report package.
- Bigger offline landmark dataset for Egypt-focused CTF/geolocation practice.
- Better country/region classifier for Arabic, Egypt, Gulf, UK/US/global clues.
- OCR Search Query Builder v2 for Arabic phrases, phone numbers, coordinates, domains, and map labels.
- Image Existence Intelligence: local hash/fingerprint/duplicate/landmark-match summary.
- Privacy-gated online search policy: external lookups remain manual and require explicit privacy review.
- Release cleanup: one-folder PyInstaller production spec, screenshots allowed, patch notes organized, and core services converted to packages.


GeoTrace Forensics X is a polished desktop digital-forensics workspace for **image metadata extraction, GPS/geolocation analysis, timeline correlation, evidence hashing, duplicate clustering, OCR/entity recovery, hidden-content triage, AI-assisted risk scoring, chain-of-custody logging, and analyst-ready reporting**.

This build keeps the original Project 1 scope intact while adding an explainable **GeoTrace AI Risk Engine** that strengthens metadata anomaly detection without turning the product into a separate deepfake project.

> **Release channel:** Public Release Candidate  
> **Default posture:** offline-first, deterministic local analysis, remote AI disabled by default.  
> **Production package:** `geotrace_forensics_x.spec` excludes `demo_evidence`. Use `geotrace_forensics_x_demo.spec` only for demo/classroom builds.


---

## Screenshots

Add real screenshots before publishing the public GitHub release:

| Screen | File |
|---|---|
| Dashboard | `screenshots/dashboard.png` |
| Geo / Map Intelligence | `screenshots/geo_page.png` |
| AI Guardian | `screenshots/ai_guardian.png` |
| Report Export | `screenshots/report_export.png` |
| Courtroom Verifier | `screenshots/courtroom_verifier.png` |

> The repository includes `screenshots/README.md` as a capture checklist. Do not publish placeholder images as final screenshots.

---

## Core Investigation Capabilities

- EXIF/native metadata extraction for common image formats.
- GPS coordinate decoding and map visualization.
- Screenshot-derived location clue parsing from OCR, visible text, and URLs.
- Evidence staging with source and working-copy SHA-256/MD5 verification.
- Duplicate and near-duplicate clustering using perceptual hashes plus context checks.
- Timeline generation and correlation.
- Hidden-content and embedded-string triage.
- Chain-of-custody event logging with hash chaining.
- HTML, PDF, JSON, CSV, executive, validation, and courtroom export package.
- Privacy-safe export paths, OCR/text/URL redaction, and manifest SHA-256 integrity hashes.

---

## New in v12.10.1

### Deep Image AI & Pixel Stego Hardening

- Adds offline **Deep Image Intelligence** for layout, object-like visual cues, quality flags, alpha transparency, edge density, color/texture metrics, and analyst next actions.
- Extends pixel hidden-content scanning beyond isolated channel LSB into **RGB/BGR/RGBA packed bitstreams**, second-lowest bit-plane triage, even/odd pair-balance metrics, and row-bias review.
- Connects image-detail results into OSINT Content Reader, AI Guardian, OSINT/CTF methodology, JSON export, and HTML report details.
- Keeps CTF methodology conservative: visual and pixel signals are leads, while answer readiness still needs GPS, visible coordinates, map URL, OCR labels, or independent source corroboration.


### Deep Image AI & Pixel Stego Hardening

- Removes the separate CTF navigation page from the main workspace and embeds the CTF tools inside OSINT Workbench. Legacy internal functions remain available for report/export compatibility.
- Adds `app/core/osint/ctf_methodology.py` for repeatable hacker/researcher grading: source independence, hard-anchor priority, hidden-content triage, blockers, and next actions.
- Adds a Methodology Matrix panel to the CTF section and upgrades the OSINT CTF/Hacker summary with readiness score, source-family count, and blockers.
- Keeps false-positive control strict: filename-only and visual-only hints stay low-confidence until corroborated by GPS, coordinates, OCR, map labels, or independent landmark evidence.
- Fixes a small page-bar UI issue so the active-workspace hint is visible.

### Map Intelligence v3 / CTF AI Hardening

- Adds an OSINT-owned **CTF GeoLocator** workspace for CTF/GeoGuessr-style image geolocation triage.
- Adds structured `CTFClue`, `GeoCandidate`, and `CTFGeoProfile` data contracts.
- Adds a conservative **Location Solvability Score** so the app can say whether an image has exact, strong, likely, weak, or no useful geo clues.
- Fixes duplicate Google Maps URL signals so a coordinate URL no longer becomes both a precise coordinate and a redundant generic provider row.
- Separates filename-only hints from real OCR/GPS/map evidence. A name like `cairo_scene.jpg` is now a weak triage hint, not a strong location claim.
- Adds ranked CTF candidates with the intended evidence priority: native GPS > map URL/coordinates > OCR/place labels > visual context > filename-only.
- Adds manual OSINT search pivots generated from OCR phrases, map labels, candidates, and region hints.
- Adds offline country/region classification and a small local landmark dataset foundation for future image-intelligence expansion.
- Keeps online/reverse-image workflows manual and privacy-gated by default; the app does not upload evidence automatically.
- Adds CTF writeup export from the GeoLocator page for authorised CTF/team-training reporting.

### v12.8.14 Release Cleanup

- Unified release identity across `config.py`, `README.md`, `pyproject.toml`, and `make_release.bat`.
- Hardened release cleanup to remove cache/build/temp artifacts before packaging.
- Fixed OCR-off behavior so disabled OCR cannot be overridden by forced analysis.
- Improved auto-height HTML rendering in AI Guardian/OSINT cards to avoid clipped content.
- Made case backup restore file operations rollback-safe when restore fails.
- Reconnected structured OSINT cache loading during case snapshot reloads.
- Added an OSINT Workbench preview page for hypotheses, entities, analyst decisions, OCR/region profile, privacy review, and evidence strength.

### Structured OSINT upgrade

- Adds structured `OSINTEntity`, `OSINTHypothesis`, and corroboration matrix outputs.
- Adds offline English/Arabic gazetteer matching for map/OCR place leads.
- Adds stronger map URL/coordinate parsing for Google Maps-style URLs, `geo:` URIs, DMS coordinates, and Plus Code signals.
- AI Guardian now shows hypothesis-card style OSINT output instead of only free-text notes.
- Reports include structured OSINT output while preserving privacy redaction modes.


### OSINT + Location AI Upgrade

- **OSINT Content v2**: offline, deterministic image-content reader that classifies map/location, browser, social, document, dashboard, and camera-photo artifacts.
- **Location hypotheses**: separates native GPS proof, derived geo clues, OCR/map labels, landmarks, and filename-only hints.
- **AI Guardian content card**: shows what appears inside the image, source context, sensitive OSINT pivots, and next recommended actions.
- **Forensic-safe wording**: map screenshots and OCR place names are treated as leads unless corroborated by native GPS, source-app data, share URLs, or acquisition logs.


### AI Guardian courtroom build

- Added a dedicated AI Guardian workspace for readiness, contradictions, privacy audit, OCR diagnostics, and evidence relationships.
- Added Courtroom Package Verifier for manifest hash validation and strict export leakage checks.
- Added Case Readiness Score and per-evidence Courtroom Readiness.
- Added AI Evidence Graph, AI Contradiction Explainer, and AI Next Best Action.
- Added Backup/Restore UI, migration ledger scaffold, and stable pytest markers.

### AI architecture upgrade

- Refactored the local AI layer into `app/core/ai/` with separate feature extraction, detectors, planning, and result models.
- Added AI priority ranking, per-evidence action plans, corroboration matrix rows, and case-link explanations.
- Upgraded the local rule-based agent to use batch AI context, duplicate peers, source-profile distribution, and courtroom caveats.
- Kept the AI layer deterministic and offline by default, so no evidence leaves the analyst machine.


### P0 Hardening

- **README/version alignment**: project identity now matches `APP_VERSION = 12.10.1`.
- **Report privacy hardening**: JSON, HTML, PDF, executive, validation, and courtroom outputs now share the same `redacted_text` privacy level for paths, OCR text, URLs, usernames, emails, and location entities.
- **AI findings now affect scoring**: the AI layer no longer only appears as a UI insight; its explainable score delta is merged into the case risk pipeline.
- **Report visibility**: AI flags, score deltas, and summaries now appear in HTML/PDF/JSON/CSV/courtroom/executive outputs.
- **Main window refactor**: analysis, case actions, filtering, timeline, and geo page logic moved from `main_window.py` into focused UI mixins.
- **Snapshot recovery logging**: corrupted primary snapshots now trigger a warning and fallback to `case_snapshot.json.bak` when available.
- **Conservative scoring**: AI deltas are capped and recorded in the score breakdown so they remain reviewable.

### P1 AI Features

- **AI Location Outlier Detection**  
  Finds evidence items that are geographically inconsistent with the rest of the case.

- **AI Timeline / Impossible Travel Detection**  
  Flags suspicious movement between timestamped geo points, such as unrealistic travel speeds.

- **AI Metadata Authenticity Cluster**  
  Looks for combined authenticity cues such as editor software, timestamp conflicts, missing EXIF on photo-like sources, hidden-content indicators, parser issues, and derived-only geolocation.

- **Optional ML Backend + Safe Fallback**  
  Uses `scikit-learn` IsolationForest for geographic outlier detection when installed from `requirements-ai.txt`. If unavailable, the engine falls back to transparent median-distance heuristics.

---

## AI Risk Engine Output

Each evidence item now stores:

- `ai_provider`
- `ai_score_delta`
- `ai_confidence`
- `ai_risk_label`
- `ai_summary`
- `ai_flags`
- `ai_reasons`
- `ai_breakdown`

These values are merged into:

- Review confidence tree
- Score breakdown
- Analyst verdict
- Courtroom notes
- HTML/PDF reports
- JSON/CSV exports
- Executive and validation summaries

Example output:

```text
AI-assisted review: AI review recommended
Score delta: +22
Flags: impossible_travel
Reason: Timeline/geography conflict between IMG-001 and IMG-002 requiring unrealistic travel speed.
```

---

## Release & Packaging

Public production releases should be created with:

```powershell
make_release.bat
```

This script cleans cache/build artifacts, runs compile checks, runs the pytest suite, builds the production EXE, creates a release ZIP, and writes `SHA256SUMS.txt`.

Manual Windows gate before publishing:

```powershell
.\build_windows_exe.bat
dist\GeoTraceForensicsX\GeoTraceForensicsX.exe
```

Required release documents are included:

- `LICENSE`
- `PRIVACY.md`
- `SECURITY.md`
- `DISCLAIMER.md`
- `THIRD_PARTY_NOTICES.md`
- `RELEASE_CHECKLIST.md`

---

## Supported Formats

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF via `pillow-heif`

---

## Quick Start

```powershell
python -m pip install -r requirements.txt
python main.py
```

Optional AI/ML backend for IsolationForest geo-outlier detection:

```powershell
python -m pip install -r requirements-ai.txt
```

For Windows convenience:

```powershell
setup_windows.bat
run_windows.bat
```

---

## OCR / Tesseract Setup

GeoTrace uses `pytesseract` as the Python bridge, but the Tesseract OCR engine itself must be installed on the operating system. Without it, the app still runs, but OCR-derived text, usernames, URLs, and map-label extraction will be limited.

### Windows

1. Install the Tesseract OCR Windows build.
2. During setup, keep the default install path if possible:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

3. Add the install folder to the Windows `PATH` environment variable.
4. Restart PowerShell or Command Prompt.
5. Verify installation:

```powershell
tesseract --version
```

### Linux / Kali / Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y tesseract-ocr
# Optional Arabic OCR language pack for Arabic map labels / visible text:
sudo apt install -y tesseract-ocr-ara
tesseract --version
```

### macOS

```bash
brew install tesseract
tesseract --version
```

If OCR does not work on Windows, confirm that `tesseract.exe` is discoverable from the same terminal used to launch GeoTrace. `pytesseract` alone is not enough; it only calls the native Tesseract engine. If PATH is locked down, set `pytesseract.pytesseract.tesseract_cmd` to the full executable path in a local environment-specific launcher.

---

## Investigation Workflow

1. Create or switch to a case.
2. Import image files or a folder.
3. GeoTrace stages a working copy and verifies source/working hashes.
4. The pipeline extracts metadata, timestamps, GPS, OCR clues, visible URLs, hidden strings, and structural trust signals.
5. Duplicates and scene groups are correlated.
6. **GeoTrace AI Risk Engine** reviews the full batch for geo outliers, timeline contradictions, and authenticity cue clusters.
7. Analyst reviews the verdict, confidence tree, map, timeline, hidden scan, and metadata tabs.
8. Export the forensic package.

---

## Project Structure

```text
app/
  agents/              Local agent contracts and rule-based assistant bridge
  core/
    ai_engine.py       AI-assisted batch risk scoring engine
    anomalies.py       Rule-based forensic anomaly scoring
    case_manager/      Investigation pipeline package and compatibility export
    exif_service.py    Metadata, EXIF, OCR, hidden-content helpers
    report_service/    HTML/PDF/JSON/CSV/report package generation package
    models.py          EvidenceRecord and case data models
  ui/                  PyQt5 interface, review panels, charts, dialogs
    mixins/            Split UI logic for reports, review, analysis, case actions, filtering, timeline, geo, charts, and preview actions
assets/                App icon and splash assets
demo_evidence/         Demo corpus and validation ground truth
tests/                 Core, report, UI state, and agent contract tests
```

---

## Forensic Interpretation Notes

GeoTrace scores are **triage aids**, not courtroom conclusions. The AI engine is designed to surface suspicious patterns and explain why an item deserves review. The analyst must still corroborate findings with source device data, application logs, witness timelines, cloud records, or independent forensic tools.

---

## Validation & Demo

The included `demo_evidence/` corpus can be used for a live classroom demonstration covering:

- EXIF/GPS recovery
- Screenshot-derived map clues
- Duplicate detection
- Hidden-content scan
- AI-assisted geo/timeline review
- Exported report package

---

## Build Identity

- App: GeoTrace Forensics X
- Version: `12.10.13`
- Channel: `Public Release Candidate`
- Intended use: academic digital-forensics investigation demo and validation workflow

## v12.8.17 Map Intelligence v3 / CTF AI Hardening

This build adds the OSINT-owned CTF GeoLocator foundation: clue cards, ranked geo candidates, Location Solvability Score, manual search pivots, and CTF writeup export. Filename-only hints are kept separate from OCR/GPS/map evidence so CTF triage remains useful without overstating proof.

New report artifact:

- `osint_appendix_<privacy>.txt` — structured hypotheses, entities, place rankings, CTF candidates/clues, OCR region signals, and analyst decisions with privacy-aware redaction.