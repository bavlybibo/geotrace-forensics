# GeoTrace v12.10.2 — Codebase Organization Pass

This release is intentionally **organization-only**. It does not introduce new
analysis features. The goal is to reduce future risk by creating clearer package
boundaries while preserving backwards-compatible imports.

## What changed

| Previous module | New implementation module | Compatibility kept |
|---|---|---|
| `app.core.exif_service` | `app.core.exif.service` | yes |
| `app.core.visual_clues` | `app.core.vision.visual_clues_engine` | yes |
| `app.core.anomalies` | `app.core.anomaly_detection.service` | yes |
| `app.core.map_intelligence` | `app.core.map.intelligence` | yes |
| `app.core.case_manager.service` | `app.core.case_manager.engine` | yes |
| `app.core.report_service.service` | `app.core.report_service.engine` | yes |
| `app.ui.main_window` | `app.ui.window.main_window` | yes |
| `app.ui.pages.ctf_geolocator_page` | `app.ui.pages.ctf.geolocator_page` | yes |

## Design rule

Old imports remain valid. New work should prefer the implementation packages.
Compatibility facades are small and exist only to avoid breaking tests, tools,
and older scripts.

## Next safe refactor steps

1. Split `case_manager.engine` into ingestion, record_builder, snapshot, backup,
   and validation modules.
2. Split `report_service.engine` into json_exporter, html_exporter, pdf_exporter,
   privacy, and package_manifest modules.
3. Split `exif.service` into gps, timestamps, payloads, and image_info modules.
4. Split `ui.window.main_window` into header, dashboard, reports, cases, and
   shell components.
