# GeoTrace Forensics X v10 — Implemented Upgrade Set

## Product-facing upgrades
- Onboarding flow on first run
- Settings dialog with persistent preferences
- Dedicated Cases page with snapshot reopening
- Recent cases dialog
- Better search/filter/sort/bookmark workflow
- Compare mode and duplicate review dialog
- Timeline narrative generation
- Audit filter + copy workflow
- Report branding/version/footer/limits
- Export validation and completion toasts
- Graceful error log panel + file logging
- Drag & drop intake
- Queued batch imports

## Release-facing upgrades
- Version constants centralized in `app/config.py`
- README and changelog aligned with v10 release candidate naming
- Windows PyInstaller packaging scaffolding added

## Remaining recommended follow-up
- Build and verify the actual Windows `.exe`
- Add large-batch performance tests
- Add UI screenshots to the README
- Replace Pillow deprecation path in EXIF service
