# GeoTrace Validation Dataset Layout

This folder is for a labelled validation dataset, not a demo-only claim. Put real fixtures in subfolders and keep the ground-truth JSON updated.

Recommended folders:

```text
validation_cases/
  gps_native/
  map_screenshots/
  no_gps_exports/
  privacy_sensitive/
  hidden_payload/
  corrupt_or_tampered/
```

Accuracy should be reported from `app.core.validation_accuracy.build_accuracy_report(records, ground_truth_path)` and the resulting pass-rate, misses, and skipped checks should be exported with the report package.

Important wording:

- `has_gps=true` means Native EXIF GPS only.
- `derived_geo=true` means OCR/map URL/visible coordinates or offline geocoder; it is not native GPS.
- `map_detected=true` means Map Screenshot Mode should activate.
- `hidden_payload=true` must only be used on known safe synthetic fixtures or lab-created artifacts.
