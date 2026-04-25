# GeoTrace Forensics X v12.8.12 — Structured OSINT Upgrade

## Goal
This build turns the OSINT layer from free-text observations into structured, analyst-safe outputs that can support the next OSINT Workbench release without weakening the forensic foundation.

## Added
- New `app/core/osint/` package:
  - `models.py` with `OSINTEntity`, `OSINTHypothesis`, `CorroborationItem`, and `OSINTSignalProfile` dataclasses.
  - `gazetteer.py` with offline English/Arabic Egypt place aliases and landmark matching.
  - `map_url_parser.py` with Google Maps, Apple/OpenStreetMap-style provider detection, `geo:` URI parsing, decimal coordinates, DMS coordinates, and Plus Code signal detection.
  - `entities.py` for deterministic URL, username, email, phone-like, date, and time pivot extraction.
  - `hypothesis.py` to generate conservative proof/lead/weak-signal OSINT hypotheses.
  - `pipeline.py` to combine entities, map signals, hypotheses, and corroboration rows.
- Evidence records now store `osint_entities`, `osint_hypothesis_cards`, and `osint_corroboration_matrix`.
- AI Guardian now renders OSINT output as structured hypothesis cards instead of plain text only.
- JSON and HTML reports now include structured OSINT cards/entities with existing privacy redaction controls.
- Map Intelligence now uses the new map URL parser and expanded offline gazetteer.
- Derived geo parsing now supports the shared map URL parser before falling back to legacy coordinate regexes.
- Added regression tests for OSINT dataclasses, Arabic gazetteer matching, map URL parsing, DMS parsing, entity extraction, and lead-vs-proof classification.

## Safety posture
- Map screenshots remain `lead` or `weak_signal` unless native GPS or strong corroboration exists.
- Visible map URLs and OCR labels are treated as displayed/searched context, not device physical location by default.
- Sensitive pivots are marked for privacy review before export.

## Validation performed in this patch
- Targeted syntax compilation for modified modules.
- Direct execution of the new structured OSINT regression tests.

## Not included yet
- Full OSINT Workbench page.
- Analyst verification buttons.
- Entity graph visualization.
- Optional local vision model.
- Full Windows EXE build validation.
