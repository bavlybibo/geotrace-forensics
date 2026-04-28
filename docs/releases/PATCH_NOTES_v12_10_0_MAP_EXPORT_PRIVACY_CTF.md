# GeoTrace Forensics X v12.10.0 — Map Answer Readiness + Export Privacy Hardening

## Focus

This patch makes the demo and analyst workflow clearer in three high-impact areas:

1. Reports/Export and Privacy posture.
2. CTF Answer Readiness.
3. Map Intelligence and map output behavior.

## Map Intelligence

- Added richer offline visual map profiling:
  - Route / navigation map
  - Road / tiled map canvas
  - Dark road/navigation map
  - Satellite / terrain-like map
  - Transit / multi-line map
- Added map answer readiness score and label.
- Added map anchor status to separate:
  - GPS / exact coordinate anchors
  - map URL / place anchors
  - OCR/place label leads
  - visual-only context
- Added map extraction plan for each record.
- MapService can now open an intelligence board when no coordinates exist.
- Approximate known-place plotting is clearly labeled as approximate.

## Reports / Privacy

- Reports page now exposes package status, privacy gate, verification, and CTF readiness metrics.
- Internal Full export now asks for explicit confirmation.
- Export summary warns that Internal Full is not share-safe.

## CTF Answer Readiness

- CTF Answer Engine now avoids treating visual-only map context as a final answer.
- Best answer remains `No stable answer yet` unless a hard anchor or place anchor exists.
- CTF methodology now includes map answer readiness in hard-anchor and candidate-validation phases.

## Validation

Run on Windows before demo:

```bat
python -m compileall -q app tests main.py
python -m pytest -q
python main.py
```
