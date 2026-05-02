# GeoTrace Forensics X v12.10.5 — Map OCR Recovery Patch

## Fixed
- Map screenshots are now detected by visual map profile, not only by filename keywords.
- Generic files named like `Screenshot 2026-...png` now auto-escalate to `map_deep` OCR when the pixel profile looks like a tiled map.
- OCR cache key bumped to prevent stale low-quality OCR results from hiding new analysis.
- Added focused Google Maps context-menu OCR crops to recover visible coordinates such as `40.48168, -3.21450`.
- Added loose-but-filtered map-label extraction for country/city labels that do not contain POI suffixes.
- Added global Spain/Portugal/Iberian map seeds and city aliases for Madrid, Barcelona, Valencia, Zaragoza, Seville, Lisbon, Porto, Toulouse, Bordeaux, and surrounding region labels.
- Lowered visual map detection threshold so maps are no longer reported as `Unknown/no_signal` when clear map color/layout evidence exists.

## Expected behavior
For a Google Maps screenshot of the Iberian Peninsula/right-click context menu, the tool should now:
1. classify the evidence as a map screenshot,
2. attempt `map_deep` OCR automatically,
3. extract visible coordinate text when present,
4. rank Spain/Portugal/Madrid/Barcelona-style labels as map/location leads,
5. keep the forensic wording conservative: displayed map location is a lead unless corroborated by GPS/source URL/browser history.
