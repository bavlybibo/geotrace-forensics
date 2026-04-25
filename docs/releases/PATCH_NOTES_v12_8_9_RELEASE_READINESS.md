# GeoTrace v12.8.9 Release Readiness Patch

This patch converts the hardened map-intelligence build into a stronger public-release candidate.

## Release blockers addressed

- Production PyInstaller spec now excludes `demo_evidence`.
- Demo PyInstaller spec added separately as `geotrace_forensics_x_demo.spec`.
- Windows icon converted to `assets/app_icon.ico` and wired into both specs.
- README/config channel aligned to `Public Release Candidate`.
- Added release governance documents: `LICENSE`, `PRIVACY.md`, `SECURITY.md`, `DISCLAIMER.md`, `THIRD_PARTY_NOTICES.md`, and `RELEASE_CHECKLIST.md`.
- Added `make_release.bat` for repeatable clean/test/build/zip/checksum release creation.
- Added `build_windows_demo_exe.bat` for non-production demo builds.
- Manifest generation now hashes root-level chart assets, not only evidence preview assets.
- Courtroom verifier now validates manifest chart assets and still blocks strict-mode map leaks.
- Added release-readiness regression tests.

## Manual gates still required on Windows

- Run the full pytest suite on Windows.
- Build the production EXE.
- Launch and smoke-test from `dist`.
- Capture real UI screenshots and place them under `screenshots/`.
