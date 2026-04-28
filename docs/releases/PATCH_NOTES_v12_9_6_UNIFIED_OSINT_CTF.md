# GeoTrace v12.9.6 — Unified OSINT/CTF Methodology Hardening

## Goal

Reduce duplicated OSINT/CTF UI surface and make the image-CTF workflow follow a clearer researcher methodology.

## Changes

- Removed the standalone **CTF GeoLocator** entry from the main workspace navigation.
- Kept legacy `CTF GeoLocator` aliases so shortcuts, old settings, and internal links route to **OSINT Workbench** instead of breaking.
- Embedded the CTF workflow inside **Unified OSINT + CTF Investigation Lab**.
- Added `app/core/osint/ctf_methodology.py`:
  - evidence intake grading,
  - pixel/hidden-content triage,
  - hard-anchor priority,
  - OCR/visual narrowing,
  - candidate source-family independence,
  - blockers,
  - answer-readiness scoring,
  - next actions.
- Added **Hacker Methodology Matrix** to the CTF section.
- Upgraded OSINT summary rows with readiness score, source-family count, and methodology blockers.
- Fixed page-bar active-workspace hint visibility.
- Added regression coverage for the methodology engine.

## False-positive controls

- Filename-only hints remain weak and cannot become answer-ready by themselves.
- Visual-only map/context signals remain low-confidence until corroborated.
- Stronger readiness requires GPS, visible coordinates, map URL, OCR/map labels, or independent landmark evidence.
- Pixel/LSB findings are treated as a triage lead, not proof of location.

## Validation performed in this environment

- Manual smoke-tested `build_ctf_methodology()` and `render_ctf_methodology_text()` with synthetic records.
- AST parsing completed for the edited modules before packaging.
- PyQt runtime tests could not be executed in this Linux sandbox because PyQt5 is not installed here.
- `pytest` is not installed in this sandbox, so full test-suite execution should still be run on the Windows release machine.
