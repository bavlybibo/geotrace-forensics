# GeoTrace Forensics X v12.8.17 — OSINT CTF GeoLocator Foundation

## Implemented

- Fixed duplicate Google Maps coordinate URL signals in `app/core/osint/map_url_parser.py`.
- Split filename-only location hints away from OCR/GPS/map-derived candidates.
- Added OSINT-owned CTF data models:
  - `CTFClue`
  - `GeoCandidate`
  - `CTFGeoProfile`
- Added Location Solvability Score and conservative labels.
- Added CTF GeoLocator page inside the OSINT workflow:
  - clue cards
  - candidate ranking table
  - manual search queries
  - metadata/privacy status
  - verify/reject candidate actions
  - markdown CTF writeup export
- Added offline country/region classifier.
- Added OCR phrase search-pivot generator.
- Added local landmark dataset foundation under `data/osint/local_landmarks.json`.
- Added local image fingerprint helper for future no-upload image intelligence.
- Rewrote the courtroom package verifier into readable functions.
- Extended OSINT appendix output with CTF candidates/clues and solvability details.
- Added regression tests for filename-only weakness, URL de-duplication, OCR priority over filename, and GPS > OCR > visual > filename priority.

## Validation status

- Source-level syntax checks were performed on the modified files.
- Targeted CTF tests were added in `tests/test_ctf_geolocator_v12_8_17.py`.
- Full Windows `pytest` and EXE build must still be run on the Windows development machine because this sandbox cannot execute the Windows GUI/build pipeline.
- Real screenshots were not captured in this environment. Capture them from the Windows GUI and place them under `screenshots/` before public release.

## Required Windows commands

```bat
python -m compileall -q app tests main.py
python -m pytest -q
make_release.bat
```
