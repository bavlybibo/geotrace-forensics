# Core Architecture

## Stable compatibility facades

The v12.10.2 organization pass keeps older imports working but moves
implementation code into domain packages.

- `exif_service.py` → facade for `exif/service.py`
- `visual_clues.py` → facade for `vision/visual_clues_engine.py`
- `anomalies.py` → facade for `anomaly_detection/service.py`
- `map_intelligence.py` → facade for `map/intelligence.py`
- `case_manager/service.py` → facade for `case_manager/engine.py`
- `report_service/service.py` → facade for `report_service/engine.py`

## New-code rule

New code should import from the implementation package where possible.
Legacy import paths stay available for compatibility and tests.
