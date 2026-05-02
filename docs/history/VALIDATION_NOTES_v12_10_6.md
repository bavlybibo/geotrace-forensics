# v12.10.6 — Visual Coordinate Fallback Validation

## Fixed
- Added a Tesseract-independent visual fallback for Google Maps right-click context menu coordinates.
- The fallback detects a white map context menu, isolates the top coordinate row, recognizes only coordinate-safe characters, and accepts the result only if it matches a valid latitude/longitude decimal pair.
- Bumped OCR cache key to `v9-visual-coordinate-fallback` so old failed OCR caches are not reused.
- Expected result for the regression screenshot: `40.481680, -3.214500` as a derived visible coordinate anchor.

## Safety
- This is not general OCR and does not invent locations.
- It only promotes a finding when a valid coordinate pair is visible and recognized.
- The result remains a screenshot-derived map coordinate, not native device GPS.
