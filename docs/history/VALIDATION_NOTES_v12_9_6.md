# GeoTrace v12.9.6 Validation Notes

## What was reviewed

- Main workspace navigation.
- OSINT Workbench and CTF GeoLocator UI overlap.
- CTF candidate review flow and answer-support surfaces.
- Pixel/hidden-content findings integration with the CTF workflow.
- Version identity across `config.py`, `pyproject.toml`, `README.md`, and `CHANGELOG.md`.
- Release cleanup for Python cache/build artifacts.

## Structural result

- The standalone CTF page was removed from the main page bar.
- CTF functionality now lives inside `Unified OSINT + CTF Investigation Lab`.
- Legacy aliases still route `CTF GeoLocator`, `CTF`, and `OSINT CTF` to OSINT Workbench so older buttons/shortcuts do not break.
- The underlying `ctf_geolocator_page.py` module remains because reports, tests, and embedded UI components still depend on its render/action helpers.

## New methodology checks

The new methodology engine grades each evidence item using:

1. Evidence intake and hash presence.
2. Pixel/LSB/hidden-content triage.
3. Hard location anchors: GPS, visible coordinates, map URLs.
4. OCR/map-label and visual narrowing.
5. Candidate validation, source-family independence, analyst status.
6. Blockers and next-best actions.

## Smoke validation completed here

- Manual smoke tests passed for `build_ctf_methodology()` and `render_ctf_methodology_text()`.
- Edited Python files were reviewed and parsed during the patching pass.
- Cache cleanup removed `__pycache__`, `.pyc`, `.pytest_cache`, `build`, and `dist` outputs before packaging.

## Validation not possible in this sandbox

- Full PyQt UI launch could not be executed because PyQt5 is not installed in the sandbox.
- Full `pytest` could not be executed because pytest is not installed in the sandbox.
- Windows EXE smoke test must still be run on the Windows release machine using `make_release.bat` and the production `.spec`.

## Required Windows release checks

Run these before final public delivery:

```bat
python -m compileall -q app tests main.py
python -m pytest -q
python main.py
make_release.bat
```

Then manually verify:

- Import images.
- Open OSINT Workbench.
- Confirm CTF/Hacker section appears inside OSINT Workbench.
- Run Deep Map OCR / Extract Map Labels / Manual Crop OCR on a test image.
- Verify/reject a candidate and confirm the case snapshot saves.
- Export report package and verify OSINT appendix + OSINT/CTF writeup.
