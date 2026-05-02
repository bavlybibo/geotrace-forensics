# v12.10.12 Closure Polish Validation Notes

## What changed

- Added Executive / Analyst / Technical workspace mode profiles.
- Added internal Map Workspace with coordinate anchors, centroid, bounds, source comparison, route story, limitations, and next actions.
- Added report preview contract before export.
- Added structured failure logs in `logs/structured_failures.jsonl`.
- Validation accuracy now supports both older keys (`has_gps`, `map_detected`, `hidden_detected`) and the newer template keys (`native_gps`, `derived_geo`, `hidden_payload`, `parser_failure`, etc.). Null/blank values are skipped instead of counted as failures.
- Optional local vision model status hook added through `GEOTRACE_LOCAL_VISION_MODEL`.
- Custom offline landmark index support added through `GEOTRACE_LANDMARK_INDEX`.
- Package signatures now support optional HMAC verification through `GEOTRACE_PACKAGE_SIGNING_KEY`.

## Release gate

Run before GitHub release:

```bat
python -m compileall -q app tests main.py
python -m pytest -q
make_release.bat
```

Then manually smoke test on Windows: import image, review, map workspace, preview export, export package, verify package.
