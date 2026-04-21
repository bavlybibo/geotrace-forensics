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
