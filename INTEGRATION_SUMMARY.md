# GeoTrace Forensics X 12.4.0-integration

Implemented in this pass:

- Single-item timeline narrative now renders instead of leaving a placeholder.
- Geo page split into smaller cards: status, reasoning, and next pivots.
- Review preview stage enlarged for stronger image dominance.
- Decision rail now separates analytic confidence, evidentiary value, and courtroom strength.
- Confidence explanation rewritten as a tree so users can see why metrics differ.
- Acquisition & custody block added to the review overview.
- Duplicate / correlation explanation is shown when a cluster exists.
- Report artifact cards added to the Reports page.
- Dashboard coverage chart no longer mixes unrelated categories into one semantic axis.
- Hidden-content filtering tightened and structural noise is classified more clearly.
- OCR pipeline broadened to multiple zones for better screenshot reasoning.
- Demo evidence generator expanded to create a stronger mixed dataset.

Notes:
- Native EXIF/GPS demo richness depends on `piexif` being installed when the demo generator is run.
- The demo files included here are safe sample artifacts intended for coursework and UI validation.
