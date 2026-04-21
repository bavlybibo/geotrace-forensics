# Final Release Priority Plan

## P0 — before public release
1. Build and verify the Windows executable on a real Windows machine.
2. Run UI smoke tests with drag-and-drop, queueing, compare mode, and case reopen.
3. Validate report generation on multi-item GPS and duplicate-heavy datasets.
4. Replace the Pillow deprecation path in `exif_service.py`.
5. Add screenshot-based QA for the Review page and Cases page.

## P1 — product polish
1. Add reverse-geocoding enrichment when internet access is allowed.
2. Add deeper multi-select compare workflow.
3. Add richer export completion panel with direct open buttons.
4. Add better empty states for duplicate review and compare mode.
5. Add a Windows installer and code-signing pipeline.

## P2 — scale & validation
1. Large-batch performance testing.
2. Memory and crash telemetry.
3. More sample evidence sets with known ground truth.
4. Accessibility review for keyboard-only navigation.
5. Automated UI tests.
