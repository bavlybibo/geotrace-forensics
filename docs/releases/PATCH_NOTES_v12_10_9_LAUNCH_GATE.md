# v12.10.9 — Launch Gate & Evidence Handoff Hardening

This patch is focused on what the latest screenshots/export showed: the UI and reports are now strong, but the product needs a clearer release/handoff gate so analysts do not confuse polished output with courtroom-ready proof.

## Added
- Launch Readiness Gate engine.
- Launch Gate section in Report Builder Index JSON/Markdown.
- Launch Gate text inside Validation Summary.
- Validation ground-truth template artifact in each report package.
- Export-time explainability refresh for stale saved cases.
- Map button unlock for derived map/coordinate evidence.

## Why it matters
- Internal Full exports are now clearly treated as internal-only.
- Derived coordinates are explicitly marked as context/lead unless corroborated by source app logs, URL, native GPS, or independent history.
- No validation dataset is clearly shown as an accuracy gap, not silently ignored.
- Courtroom threshold gaps become visible before handoff.
