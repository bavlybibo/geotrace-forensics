# GeoTrace v12.10.8 — P1/P2 Continuation Patch

## Added

- Reusable local `redaction_engine` with audited hits for URLs, emails, usernames, coordinates, phone-like values, paths, and secret/token patterns.
- Tamper-evident `package_signature.json` and `package_signature.sha256` envelope for report packages.
- Verifier hook that checks the package signature envelope in addition to manifest and artifact hashes.
- Multi-case comparison helper for shared hashes, perceptual hashes, devices, place leads, and timeline overlap.
- Enterprise audit summary helper with blockers/controls for handoff readiness.
- Plugin registry entries for package signature, multi-case comparison, and enterprise audit.

## Fixed / strengthened

- Initial import now persists advanced map fields that were previously only guaranteed after manual rescan: route endpoints, label clusters, confidence radius, offline geocoder hits, source comparison, and interactive map payload.
- Dashboard Action Center now surfaces confidence radius, route endpoints, label clusters, and offline-geocoder hit count.
- Report redaction uses the shared privacy engine instead of duplicated regex snippets.

## Notes

The package signature is tamper-evident, not a legal PKI/private-key signature. It is designed to catch post-export modifications during academic/demo/courtroom-style handoff.
