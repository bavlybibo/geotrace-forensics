# GeoTrace Forensics X — User & Analyst Guide

## Recommended workflow

1. Create or open a case.
2. Import evidence into the case workspace.
3. Run the standard analysis pass.
4. For screenshots/maps, run **Deep Map OCR** and then **Manual Crop OCR** on labels, coordinates, route cards, and search bars.
5. Review the **Map Evidence Ladder** before using any location claim.
6. Use **CTF Answer Solver Mode** only after verifying candidate basis and limitations.
7. Export reports with the correct privacy level and verify the package manifest.

## Confidence meanings

- **Proof**: direct GPS, parsed coordinates, cryptographic/package integrity, or multiple independent corroborating signals.
- **Lead**: OCR/place/landmark/map URL evidence that looks useful but still needs analyst verification.
- **Weak signal**: filename-only, visual-only, or heuristic evidence that should not be reported as fact.

## Map/Geo rules

Native GPS outranks derived map coordinates. Parsed map URL/visible coordinates outrank OCR place labels. OCR labels and offline geocoder hits are leads until confirmed. Visual map colors/route overlays only prove that a map-like UI exists; they do not identify the real place alone.

## Privacy modes

- Use full export only for private/internal work.
- Use courtroom redacted export when sharing outside the team.
- Do not upload raw evidence to external reverse-image/map services without explicit approval.

## Limitations

GeoTrace is an analyst assistant. Offline OCR, image similarity, scene classification, and geocoder seeds can be wrong. The final report must preserve evidence, confidence, source, and limitations.
