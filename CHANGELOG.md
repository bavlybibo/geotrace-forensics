## v12.9.2

- Added AI Guardian v5 Deep Context Reasoner for cross-signal reasoning across GPS, OCR, map, timeline, privacy, and duplicate-group evidence.
- Added deterministic Visual Semantics AI helper for broad scene/layout classification without external model calls.
- Enhanced OSINT Content profiling with visual-semantic tags/cues and safer confidence calibration.
- Improved AI action plans and corroboration matrix with explicit location posture, timeline posture, privacy posture, and duplicate-location mismatch detection.
- Updated AI Guardian UI to show deep reasoning previews and map evidence ladder lines.
- Added regression tests for deep context reasoning and visual semantics.

## v12.9.1

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
