# GeoTrace v12.10.17 — Digital Precision Fixed Build

This build fixes the unavailable download issue and folds the digital-risk cleanup into the project as real code.

## Added
- `app/core/digital_risk.py`
- Final call: `ISOLATE / REVIEW / WATCH / CLEAR`
- Separate risk score and confidence score
- Confirmation level: `strong / medium / weak / clean`
- Danger zones: embedded strings, container/trailing bytes, RGB/alpha low-bit planes, visible-OCR-only, or none
- False-positive guardrails for visible OCR/code screenshots and JPEG low-bit noise
- Short one-line result for UI/report views
- Report JSON field: `hidden_content.digital_risk`
- AI Guardian cards now show Digital Risk Verdicts instead of noisy pixel narratives

## Safety
The layer does not execute payloads and does not claim malware confirmation from strings alone.
It reports `malware_not_confirmed_*` until a sandbox/reverse-engineering validation confirms execution.
