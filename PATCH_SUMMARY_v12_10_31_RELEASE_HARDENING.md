# GeoTrace v12.10.31 Release Hardening Patch

Applied conservative fixes while preserving the existing structure and app flow.

## Fixed
- Aligned README version with VERSION/app config (`v12.10.31`).
- Hardened place alias matching to prevent short aliases such as `la` from matching inside words like `available`.
- Updated the GPS provider bridge test to match the clearer `native_gps_bridge_ready` status.
- Reworked the release cache test so pytest does not fail on runtime-generated `__pycache__`; release hygiene remains enforced by `clean_release_artifacts.py` + `audit_release.py`.
- Added a privacy approval confirmation before opening third-party map provider links from the Map Workspace.

## Preserved
- Existing architecture, module paths, UI page layout, optional stack setup, and release scripts.
