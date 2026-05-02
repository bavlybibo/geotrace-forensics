# v12.10.31 — Stack Doctor + Recommended Optional Setup

- Added `setup_recommended_stack_windows.bat` to install the useful optional stack without pulling huge AI packages.
- Added `requirements-recommended.txt` and `requirements-ai-lite.txt` to separate safe optional dependencies from AI-heavy packages.
- Upgraded `tools/check_optional_stack.py` to show UI, Geo, Forensics, AI-heavy, OSINT cache, and GeoNames readiness in one place.
- Added `tools/stack_doctor.py` for a clearer install diagnosis and next-step recommendation.
- Added Windows optional stack documentation under `docs/INSTALL_OPTIONAL_STACK_WINDOWS.md`.
- System Health now warns clearly when GeoNames data has not been imported and when Python 3.14 is being used with AI-heavy packages.



## v12.10.30 - Optional Forensics + Heavy AI Stack

- Added optional forensics requirements for ExifTool, QR/barcode detection, ImageHash, timezonefinder, pycountry, and DuckDB.
- Added optional heavy AI requirements for Ultralytics YOLO and PaddleOCR.
- Added fail-safe ExifTool, barcode, ImageHash, YOLO, timezone, country normalization, and DuckDB helper bridges.
- Integrated QR/barcode/ImageHash/YOLO outputs into Deep Image Intelligence metrics without making startup depend on heavy packages.
- Updated System Health and Dependency Check to show the new optional stack truthfully.

## v12.10.29 — Clean GeoData + Startup Sanity

- Hardened GeoNames importer for cities1000/cities5000/cities15000/allCountries.
- Added alternateNamesV2/country/admin/timezone enrichment.
- Added fast smoke check and replaced setup compileall gate.
- Updated System Health raw GeoData detection.


# v12.10.24 — GPS Repair + Map Provider Bridge

- Repaired GPS ratio/DMS normalization so real native EXIF GPS is less likely to be missed across Pillow/exifread formats.
- Added privacy-gated Map Provider Bridge with Google Maps, OpenStreetMap, and Apple Maps verification links from GPS, parsed map URLs, OCR coordinates, and strong place labels.
- Expanded map/coordinate parser coverage for OSM URLs, Google embedded coordinate tokens, route origin/destination params, `lat/lon` text, and Arabic coordinate labels.
- Upgraded Internal Map Workspace with External Map Bridge and Provider Verification Links panels plus an analyst-approved Open Provider Link action.
- Added bridge fields to EvidenceRecord, import/rescan pipelines, dependency/system health output, and geo/review text builders.
- Added focused tests for GPS normalization, coordinate extraction, and provider-link generation.

# v12.10.22 — System Health P2 Clean Guard

- Added in-app System Health workspace and Dependency Check.
- Added First Run Setup Wizard for safe local defaults and runtime folder creation.
- Added dependency/system-health service modules for testable release readiness.
- Added offline visual similarity search CLI and P2 readiness guidance.
- Expanded offline landmark/geocoder data and added real validation template.
- Tightened truthful local-vision wording: adapter is ready; real inference requires a configured local runner.
- Added focused tests for release/P2 assets and visual similarity support.

# v12.10.20 — AI Calibrated Guardian

- Strengthened `app/core/image_risk_ai.py` with multi-sensor fusion, weighted contributor matrix, threat family, decision lane, technical-sensor count, and analyst verdict hints.
- Added a privacy floor and stronger false-positive caps: visible code, GPS, map screenshots, and personal data are review/redaction signals unless byte/container/pixel evidence corroborates technical danger.
- Refreshed AI Guardian page colors with `AIGuardianHero`, semantic metric pills, and risk-state HTML cards for SAFE/LOW/MEDIUM/HIGH/CRITICAL.
- Persisted the new Image Threat AI fields into `EvidenceRecord`, case import, Guardian cards, and report JSON/HTML output.
- Added/updated focused tests for clean images, visible-code screenshots, confirmed hidden payloads, batch promotion, and privacy-only location images.

# v12.10.17 — P0 Release Ready Patch

- Added missing runtime/release files: `main.py`, `requirements.txt`, `requirements-dev.txt`, Windows setup/run/release scripts, and PyInstaller specs.
- Aligned app/docs version metadata to `12.10.17`.
- Added `tools/audit_release.py` release hygiene gate.
- Added smoke tests for release files, report preview, package signature verification, and map false-positive guards.
- Added bounded OCR global budget through `GEOTRACE_OCR_GLOBAL_TIMEOUT` and surfaced OCR/AI/privacy controls in Settings.
- Hardened map/place candidate filtering to reject metadata/demo noise such as `exif`, `image`, `metadata`, and blank white canvases.
- Added validation/benchmark and offline landmark seed files.

---

# Changelog

## v12.10.13 — Release Hygiene & Security Closure

- Aligned version metadata across application config, packaging, installer, and dependency lock notes.
- Cleaned README and archived older patch notes under `docs/history/`.
- Removed runtime cache/compiled Python artifacts from the source package.
- Added `tools/audit_release.py` for version/cache/silent-exception/AST checks.
- Replaced remaining silent broad exception handlers with structured/non-fatal logging.
- Hardened package signature verification and reduced local-path leakage in signature metadata.
- Added coordinate range validation before map reconstruction accepts anchors.

# v12.10.7 — P0/P1 World Readiness Patch

## Added
- OCR Setup Wizard for Tesseract/path/language-pack readiness.
- Dashboard Evidence Viewer plus Action Center for selected-evidence next actions.
- Claim-to-evidence linking with exportable Claim Matrix.
- Report Builder Index Markdown/JSON artifacts in every package.
- Timeline Confidence Model and Validation Accuracy helper.
- Lightweight Plugin Registry for future OCR/map/AI/export engines.

## Improved
- Reports page now surfaces Claim Matrix and Report Builder artifacts.
- JSON export includes claim links and timeline confidence profiles.
- OSINT visual cue fallback logs debug details instead of silently passing.

## Validation
- Added release notes and validation checklist; Windows EXE build must still be run on the target Windows machine.

# v12.10.4 — AI Reasoning Strategy & Image Review Pipeline

## Added
- Added a deterministic image reasoning strategy layer on top of deep image intelligence.
- Added OCR/map/geolocation/hidden-content/detail-complexity priority scores to `image_detail_metrics`.
- Added quality gates and corroboration targets so heuristic visual cues cannot be accidentally worded as facts.
- Promoted image reasoning strategy into batch AI actions and corroboration matrix lines.
- Displayed strategy scores and corroboration targets in AI Guardian, OSINT Workbench, and HTML reports.

## Improved
- Image summaries now identify the chosen review strategy instead of only listing visual cues.
- Methodology steps now include strategy gate and corroboration target guidance.
- OSINT Content v2 uses the strategy layer as an analyst-safe cue, not as object recognition.

## Validation
- Added focused tests for reasoning strategy scoring and batch AI promotion.
- Syntax validation and focused manual functional checks were run for the changed modules; targeted pytest was attempted but interrupted by the sandbox execution window.

# v12.10.3 — Deep Image Methodology & AI Detail Upgrade

- Added tile-level Deep Image Intelligence with attention region boxes, crop/OCR priority reasons, scene descriptors, and methodology steps.
- Promoted image detail methodology into OSINT Content, CTF Answer Readiness, AI Guardian, and JSON/export profiles.
- Kept the image pipeline offline and bounded with thumbnail + 4x4 grid analysis to preserve UI/import responsiveness.
- Added regression tests for attention-region generation, OSINT content consumption, and batch AI action planning from deep image methodology.


## v12.10.0 — Map Answer Readiness + Export Privacy Hardening

- Added richer visual map-type profiling for route/road/dark/satellite-terrain/transit-like screenshots.
- Added map answer-readiness score and anchor-status wording so visual-only map context cannot become a fake location answer.
- Added map extraction plans for GPS/coordinate/map URL/OCR/place-label workflows.
- Enhanced CTF Answer Engine and methodology with map answer readiness.
- Hardened Reports/Export UI metrics for package, privacy gate, verification, and CTF readiness.
- Added Internal Full export confirmation warning and stronger share-safety wording.
- MapService now opens a map intelligence board for map screenshots without coordinates and plots approximate known-place leads only when dictionary/OCR/place anchors exist.

# v12.9.9 — Premium Demo UI System

- Added a dashboard Mission Control hero with workflow/readiness KPI pills.
- Reduced blank space in dashboard chart cards and duplicate review panels.
- Upgraded Geo Review into a location-intelligence board with native GPS, derived context, candidate place, and route-signal KPI pills.
- Rebuilt Reports & Export into a command-center layout with package metrics, full-package action, 3-column artifact grid, and compact status panels.
- Added `app/ui/design_system.py` to document reusable visual tokens and page intent.
- Added new QSS selectors for HeroPanel, GeoSignalRail, ReportArtifactCard, and stronger premium demo styling.

## v12.9.7
- Added Deep Image Intelligence module for deterministic visual details: layout hints, object-like cues, quality flags, edge density, color/texture ratios, and next actions.
- Hardened Pixel Stego analysis with composite RGB/BGR/RGBA streams, bit0/bit1 checks, even/odd pair-balance metrics, and row-bias triage.
- Integrated deep image signals into OSINT Content Reader, AI Guardian, OSINT/CTF methodology, JSON export, and HTML reports.
- Added tests for RGB-packed LSB payload recovery, image detail UI-like analysis, and CTF methodology support from deep visual details.

## v12.9.6

- Merged the duplicated CTF navigation into the OSINT Workbench as one unified OSINT + CTF Investigation Lab.
- Added `app/core/osint/ctf_methodology.py` with hacker/researcher readiness scoring: evidence intake, pixel hidden-content triage, hard anchors, OCR/visual narrowing, candidate validation, blockers, and next actions.
- Added a Hacker Methodology Matrix panel and upgraded the OSINT CTF/Hacker summary with readiness labels, source-family counts, and blockers.
- Added compatibility aliases so older CTF links/shortcuts route to OSINT Workbench instead of breaking.
- Fixed the workspace page-bar hint so release identity is visible in the UI.

## v12.9.5

- P0 demo hardening: unified version identity across config, README, pyproject, and release scripts.
- Fixed CTF GeoLocator render return bug by removing stale `RETURN_JOIN_LINES_PLACEHOLDER` markers.
- Immediate CTF actions: Deep Map OCR and Extract Map Labels now rescan the selected/top evidence item instead of only preparing the next import profile.
- Added Manual Crop OCR for CTF/map evidence using a safe center-map crop and merge-back workflow.
- Added CTF render/contract regression tests for candidate detail, answer engine, question matrix, rescan backend, and report artifact packaging.
- AI Guardian summary now renders as compact readiness cards instead of one long terminal-style text block.
- Timeline chart upgraded to a larger source-aware analyst view with clearer labels and parser/risk cues.
- Report packages now include a first-class CTF GeoLocator markdown writeup and artifact card.
- Central logging is initialized at startup through `logs/geotrace.log`.


- Map Intelligence v3: added a visible Map Evidence Ladder that separates native GPS, visible coordinates/map URLs, OCR labels, known city/area/landmark hits, visual map context, and filename-only hints.
- CTF AI hardening: visual-only map screenshots now stay conservative (`Map context only — no stable location`) and no longer receive an inflated city/area solvability label.
- CTF candidate review: rejected candidates are pushed below active candidates and are excluded from the live writeup top-candidate section.
- Image Existence Intelligence: fixed false `near_duplicate=True` when the similarity note says no near-duplicate was identified.
- UI polish: dark styled Candidate Ranking table plus Deep Map OCR and Extract Map Labels controls.
- OSINT quality: semantic deduplication for repeated visual clues and a larger offline landmark/country-region knowledge base.
- Cleanup retained from v12.9: production PyInstaller one-folder spec, safer release script, screenshots allowed in VCS, patch notes under docs/releases, and package-compatible case/report services.

## v12.8.17-ctf-foundation

- Added OSINT-owned CTF GeoLocator data contracts: `CTFClue`, `GeoCandidate`, and `CTFGeoProfile`.
- Added Location Solvability Score and CTF writeup generation.
- Fixed duplicate Google Maps coordinate URL signals.
- Separated filename-only location hints from OCR/GPS/map evidence so filenames stay weak signals.
- Added CTF GeoLocator workspace with clue cards, candidate ranking, search queries, metadata/privacy status, verify/reject actions, and writeup export.
- Added offline country/region classifier, OCR search pivot generator, local landmark dataset foundation, and local image-fingerprint helper.
- Rewrote `app/core/reports/verifier.py` into readable, maintainable functions.
- Added regression tests for filename-only weakness, URL de-duplication, OCR-over-filename priority, and GPS > OCR > visual > filename priority.

## v12.8.14-release-cleanup-rc1

- Unified release identity across config, README, pyproject, and release script.
- Fixed OCR-off behavior, AI Guardian HTML auto-height/scroll, rollback-safe backup restore, and OSINT cache reload.
- Added OSINT Workbench page with hypothesis cards, entity graph, analyst decision buttons, OCR/region profile, privacy review, evidence-strength wording, and next-scan profile controls.
- Added dedicated OSINT Appendix artifact to report packages.
- Added clearer migration ledger registry and map/vision helper modules for future refactor work.

## v12.8.12-structured-osint
- Added a structured OSINT package with serialisable entity, hypothesis, and corroboration dataclasses.
- Added offline English/Arabic gazetteer matching and stronger map URL/coordinate parsing.
- Wired structured OSINT cards into AI Guardian and report exports while preserving privacy redaction.
- Kept map screenshots conservative: displayed place evidence is a lead unless native GPS/source-app corroboration exists.

## v12.7.4-refactor
- Split startup splash rendering into `app/ui/splash.py` and kept `main.py` as a small bootstrap file.
- Moved `AnalysisWorker` and `ReportWorker` to `app/ui/workers.py`.
- Extracted record narrative builders, dashboard chart rendering, and preview interactions into focused UI mixins.
- Added `app/agents/` with a stable `ForensicAgent` protocol and a safe local rule-based default agent.
- Added an Agent Bridge panel in the Review decision rail for future AI-agent integration without UI rewrites.
- Kept the duplicate false-positive hardening while restoring strong pHash+size near-duplicate coverage.

## Hotfix v12.7.1
- Fixed Windows startup import path resolution for packaged/extracted runs.
- Switched key UI/service imports to package-relative imports with safe fallback.
- Prevented ModuleNotFoundError on startup in some extracted environments.

# Changelog

## 12.3.0-clarity
- Improved preview stage, report hub, and decision rail clarity
- Added evidentiary value as a separate metric from analytic confidence
- Fixed timeline narrative generation
- Upgraded map output and report visuals
- Reduced hidden-string noise and improved presentation polish

# Changelog

## 12.2.0-polish — presentation and workflow polish
- Fixed the startup mismatch where an active case could show analyzed evidence counts before the left evidence rail was populated.
- Reduced top-bar clutter by keeping only core actions visible and moving secondary actions into a compact More menu.
- Reworked the preview stage with shorter controls, larger canvas space, calmer empty states, and cleaner badge wording.
- Hid meaningless zero-state decision widgets until an evidence item is selected.
- Added a confidence explanation panel that surfaces anomaly contributors and score-breakdown details.
- Tightened spacing, borders, tab widths, button widths, and scroll behavior to reduce clipping and overflow.
- Added screenshot previews to exported HTML and PDF reports through generated report assets.
- Cleaned project packaging by targeting a leaner handoff build with caches and obsolete implementation notes removed.

## 11.0.0-rc1 — Review rebuild and forensic-depth pass
- Fixed review-state inconsistencies so cases with evidence always auto-select a visible item after filtering.
- Removed auto-navigation side effects from clear/reset flows.
- Rebuilt the preview control bar into grouped rows to avoid clipped labels and improve fullscreen/export access.
- Upgraded the evidence rail with richer cards, risk accents, score chips, and supporting confidence metadata.
- Added timestamp confidence, GPS verification posture, anomaly contributors, courtroom notes, and richer hidden/code summaries.
- Expanded export packaging with executive summary, validation summary, and export manifest outputs.
- Added stronger validation helpers, compare-candidate support, and custody event summaries.
- Refreshed demo-evidence generation and expanded automated test coverage.

## 10.2.0-rc1 — Review workflow and hidden-content pass
- Fixed top-bar overflow by separating action controls from case-switch/status rows and shortening crowded labels.
- Rebuilt the Review center around true tabs: Preview, Overview, Metadata, Hidden / Code, Notes, and Audit.
- Increased preview stage size, added fullscreen controls, added review-export action, and surfaced keyboard hints.
- Simplified the decision rail by removing duplicated pivot blocks and keeping score, confidence, verdict, and next steps.
- Added hidden-content scanning for readable strings, URLs, and code-like markers embedded in image containers.
- Improved search with token filters like `gps:yes`, `risk:high`, `parser:failed`, `hidden:yes`, `url:yes`, `tag:...`, and `note:...`.
- Wired real timeline narrative generation, stronger custody badges, and case cards for the Cases page.
- Strengthened compare mode visuals and removed the Pillow perceptual-hash deprecation warning.

## 10.1.0-rc1 — Review page polish
- Rebuilt the Review page around a permanent evidence stage plus lower detail tabs.
- Moved notes, raw tags, metadata, and audit focus into dedicated tabs so the center stage stays clean.
- Added a forensic fallback panel for malformed/unsupported assets instead of surfacing raw dumps in the stage.
- Simplified the right rail into a calmer decision layout with clearer next steps.
- Applied a dark themed settings/onboarding dialog pass for readability and visual consistency.

## 10.1.1-rc1 — Stylesheet syntax hotfix
- Fixed a stylesheet packaging error in `app/ui/styles.py` that caused startup to fail with `IndentationError`.
- Verified project compilation and test pass after the fix.

## 10.0.1-rc1
- Startup hotfix: registered the Cases workspace page in the stacked workspace to resolve the launch-time `KeyError: 'Cases'`.
- No feature removals. Existing v10 additions remain intact.


## v12.8.0-ai-risk

- Added GeoTrace AI Risk Engine with location outlier, impossible travel, and metadata authenticity cluster review.
- Merged AI score deltas into the main risk pipeline and reports.
- Hardened exported HTML privacy path handling.
- Updated README/build identity to match the new AI-assisted build.

## v12.8.15-codebase-osint-workbench-rc1
- Added safe codebase cleanup modules for visual map scoring and map evidence-strength policy.
- Added dedicated OSINT Appendix report artifact and included it in package payloads.
- Improved OSINT Workbench with next-scan region/OCR profile controls and clear status text.
- Kept map/location wording conservative: visual signals are investigation pivots, not proof.

## v12.8.16 Report + OSINT Polish RC1

- Fixed PDF Evidence Matrix wrapping/overlap in generated reports.
- Fixed OCR attempted/no-text wording so reports do not say OCR was not attempted after a quick/deep OCR run.
- Added weak-signal hypothesis cards for visual map/navigation screenshots with no stable place label.
- Improved OSINT Workbench active/selected profile messaging.
- Updated release identity to 12.8.16-report-osint-polish-rc1.

## v12.10.14 — AI Layer Upgrade Patch

- Added a real offline Local LLM command adapter with schema guard and deterministic fallback.
- Added optional Local Vision command execution for caption/object/landmark candidate JSON.
- Added deterministic semantic image fingerprinting for local similarity and visual-family triage.
- Added Evidence Fusion Guard: claim-to-evidence matrix rows, limitations, contradictions, and next actions.
- Extended validation metrics to cover image detail, semantic fingerprints, local vision execution, route detection, and OCR confidence thresholds.
- Updated plugin registry with explicit AI/vision extension points.

## v12.10.24 — Map & AI Precision Polish

- Added strict claim policies for Native GPS, Derived Geo Anchor, Map Search Lead, and Map Screenshot Mode.
- Prevented offline geocoder/city centroid candidates from being treated as exact coordinate/GPS proof.
- Added conservative uncertainty radii for exported map markers.
- Reduced filename-only map false positives.
- Added AI risk split cards to separate technical payload risk from privacy, geo, and manipulation risk.
- Added targeted tests for map/AI claim precision.
