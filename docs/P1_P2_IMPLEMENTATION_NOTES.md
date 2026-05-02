# P1/P2 implementation notes — v12.10.17

## Implemented/foundation present

- Import/onboarding and OCR setup wizard are available from the UI.
- Evidence viewer includes preview, metadata, notes, audit, and scoring sections.
- Digital Risk verdict fields and AI Guardian cards are generated locally.
- Report preview is available before export.
- Redacted export modes and package verification are available.
- Settings expose OCR mode, OCR timeout, OCR global budget, OCR max calls, log privacy, and optional local AI toggle.
- Validation dataset seed and benchmark CLI were added.
- Offline landmark seed was added for local expansion.

## Still optional/advanced

- Local vision model requires a real local model adapter path and approved evidence-handling policy.
- Large landmark/geocoder databases should be shipped separately from source packages.
- Demo video/screenshots should be generated from the final EXE build, not from source-only review.
