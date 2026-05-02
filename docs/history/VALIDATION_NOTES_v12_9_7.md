# GeoTrace v12.9.7 Validation Notes

## Static validation performed here

- AST syntax parsing passed for all modified Python files.
- Compile check passed:

```bat
python -m compileall -q app tests main.py
```

## Focused tests passed here

Executed with plugin autoload disabled because the sandbox Python site startup hangs with the default venv launcher:

```bat
python -m pytest -q tests/test_pixel_stego_v12_9_5.py tests/test_image_intelligence_v12_9_7.py tests/test_ctf_methodology_v12_9_6.py
```

Result: **7 passed**.

## Full-suite note

A full `pytest -q` run timed out in this sandbox before completion. Run it on the Windows release machine after installing project requirements.

## Required Windows validation before final handoff

```bat
python -m compileall -q app tests main.py
python -m pytest -q
python main.py
make_release.bat
```

## Manual flows to verify

1. Import a normal screenshot and verify Deep Image Intelligence appears in OSINT Workbench and AI Guardian.
2. Import a PNG with RGB-packed LSB text and verify Pixel Hidden-Content Scan shows readable stream output.
3. Export JSON/HTML reports and confirm `image_detail_profile` and `pixel_forensics` sections are present.
4. Confirm CTF/Hacker Summary still refuses filename-only answers as proof.
5. Confirm old v12.9.6 case snapshots load with default v12.9.7 image-detail fields.
