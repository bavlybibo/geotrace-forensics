# v12.9.2 — AI Guardian v5 / Deep Context Reasoner

## Added

- `app/core/ai/context_reasoner.py` for cross-signal reasoning across location, time, privacy, duplicate, hidden-content, and source-profile context.
- `app/core/ai/visual_semantics.py` for deterministic local visual-layout classification.
- Regression tests in `tests/test_ai_deep_context_v12_9_2.py`.

## Improved

- AI batch assessment now adds reasoning rows to the corroboration matrix, confidence basis, and next-best actions.
- OSINT content profiling now uses visual-semantic cues in addition to OCR/source/map signals.
- AI Guardian UI now surfaces deep reasoning and evidence-ladder snippets.

## Safety posture

- The AI remains offline/deterministic by default.
- Map screenshots and route overlays are treated as displayed/searched-place leads, not physical-device proof, unless native GPS or source-app records corroborate them.
