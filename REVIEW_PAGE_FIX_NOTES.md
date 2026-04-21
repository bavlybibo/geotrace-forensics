# GeoTrace V9.1 Review Page Fix

This patch focuses only on the Review page, which was visually broken in the previous V9 build.

## What changed
- Rebuilt the Review page into a cleaner 3-lane structure with safer width constraints
- Added a vertical splitter in the center lane so the preview stage stays dominant
- Turned the bottom review details into mini-pages:
  - Overview
  - Metadata
  - Notes
- Wrapped the right verdict rail in its own scroll area to prevent clipping/collapse
- Simplified the verdict rail hierarchy:
  - smaller score ring
  - confidence
  - priority facts first
  - secondary facts below
  - narrative after that
- Reduced review-page overflow pressure by shortening fallback content and trimming always-open blocks
- Kept raw metadata panels hidden by default

## Validation performed here
- `python -m compileall app main.py`
- `pytest -q` -> 7 passed

## Important note
The GUI was not runtime-opened in this environment because PyQt5 runtime is not available here, so this patch was validated through code structure, compile checks, and tests rather than live window rendering.
