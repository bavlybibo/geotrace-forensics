# Changelog

# Changelog

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

# Changelog

## 10.1.1-rc1 — Stylesheet syntax hotfix
- Fixed a stylesheet packaging error in `app/ui/styles.py` that caused startup to fail with `IndentationError`.
- Verified project compilation and test pass after the fix.

## v10.0.1-rc1
- Startup hotfix: registered the Cases workspace page in the stacked workspace to resolve the launch-time `KeyError: 'Cases'`.
- No feature removals. Existing v10 additions remain intact.

## v10.0.1-rc1
- Added onboarding flow and settings panel.
- Added case snapshots and stronger reopen workflow.
- Added drag-and-drop evidence intake and queued batch processing.
- Added compare mode, duplicate review, timeline narrative, and stronger audit trail UX.
- Added report version footer, methodology, limitations, and export validation.
- Added packaged executable scaffolding for Windows builds.
