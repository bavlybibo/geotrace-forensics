# v12.10.4 — AI Reasoning Strategy & Image Review Pipeline

This release strengthens the project methodology and AI explainability layer.

## What changed
- Added a review-strategy engine for image evidence.
- Added five bounded scores: OCR priority, map review priority, geolocation potential, hidden-content priority, and detail complexity.
- Added `quality_gate` and `corroboration_target` metrics.
- Integrated the new strategy into AI Guardian, OSINT Workbench, batch AI findings, and reports.
- Added tests for strategy scoring and action-plan promotion.

## Why it matters
The tool now tells the analyst *how to analyze the image next* instead of only describing what the image seems to contain. This keeps reports safer, more professional, and more CTF/OSINT-ready.
