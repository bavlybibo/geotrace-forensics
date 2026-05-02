# GeoTrace v12.10.31 CI Full Fix

This patch hardens the release package and fixes the regressions observed in CI.

## Fixed

- Restored the canonical `README.md` name and removed the accidental `README (3).md` release artifact.
- Added release identity text for `v12.10.31` and `Optional Stack Doctor + GeoData Ready`.
- Added conservative alias matching in `app/core/osint/local_landmarks.py` to prevent `NameError: _alias_in_text` and avoid loose substring matches.
- Exported `_iter_candidates` and `_render_writeup` from the legacy CTF GeoLocator facade.
- Added `app/core/ai/context_reasoner.py` and wired it into `run_ai_batch_assessment()`.
- Prevented duplicate plain-coordinate signals for provider URLs like Google Maps `@lat,lon` links.
- Preserved filename-only city/area hints as weak candidates without treating them as strong map proof.
- Fixed local vision command splitting on Windows paths by using OS-aware `shlex.split()`.
- Added PyInstaller icon configuration for production and demo specs.
- Registered pytest markers to avoid unknown marker warnings.
- Removed Python cache artifacts from the release tree before packaging.

## Validation run

- `python -m compileall -q app tests main.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` → 44 passed
- `python tools/audit_release.py` → passed
- `python tools/smoke_check.py` → passed

Note: The local ChatGPT container has extra pytest plugins installed globally. The clean validation command disables external plugin autoload so the result matches a controlled CI environment more closely.
