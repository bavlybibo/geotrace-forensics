# GeoTrace Forensics X — V9 Page-Based Redesign

## What changed

### Structural redesign
- Rebuilt the UI around **top-level pages** instead of one overloaded all-in-one screen:
  - Dashboard
  - Review
  - Geo
  - Timeline
  - Custody
  - Reports
- Reduced the old stacked-on-stacked layout that caused clipped panels, broken rails, and too many simultaneous scroll regions.
- Moved the app toward a **preview-first workflow** where the evidence stage is the visual focal point.

### Layout and scroll cleanup
- Removed the old giant combined workspace design.
- Converted most deep sections into **dedicated pages**.
- Kept scrolling constrained to page-level or column-level zones rather than many nested regions.
- Removed chart-in-scroll nesting for chart cards.
- Hid raw metadata panes by default.

### Review page improvements
- Review page now uses a calmer 3-column structure:
  - Evidence list
  - Hero preview stage + metadata overview + notes
  - Short verdict / pivots rail
- Added a **fullscreen preview** action.
- Kept GIF frame controls in the hero stage.
- Metadata overview is shown first; raw/normalized dumps stay collapsed until requested.

### Dashboard improvements
- KPI strip is compacted and moved to the Dashboard page.
- Case assessment and priority queue live on Dashboard instead of being squeezed into the review rail.
- Relationship, risk, source, and coverage charts moved away from the main preview stage.
- Duplicate/reuse notes remain available as a dedicated dashboard block.

### Dedicated specialist pages
- Geo page focuses on GPS state, pivots, and location reasoning.
- Timeline page focuses on timeline interpretation and adaptive single-item handling.
- Custody page is isolated as its own review area.
- Reports page is now the export/document hub.

### Visual pass
- Reduced visual heaviness from the previous version.
- Tightened spacing and lowered border aggression.
- Rebalanced colors so accent cyan is used more intentionally.
- Improved hierarchy for titles, body text, and supporting labels.

## Important note
- This version was validated through:
  - Python compile checks
  - the existing automated test suite
- GUI runtime rendering was **not** executed inside this environment because PyQt5 is not available here.
- That means the code structure, syntax, and non-UI tests were verified, but final live UI polish should still be checked on your Windows machine.

## Verified in this environment
- `python -m compileall app main.py`
- `pytest -q` → 7 passed
