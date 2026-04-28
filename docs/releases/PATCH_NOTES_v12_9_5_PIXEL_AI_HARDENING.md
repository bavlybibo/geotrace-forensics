# GeoTrace Forensics X v12.9.5 — Pixel AI & Hidden-Content Hardening

## Added
- New offline `app.core.vision.pixel_stego` module for pixel-level hidden-content triage.
- LSB bit-plane analysis for RGB/alpha channels with readable-string recovery.
- Transparent-pixel RGB residue detection for hidden data under alpha masks.
- Low-bit entropy and compression metrics per channel.
- Pixel findings are now attached to every `EvidenceRecord` and exported in JSON/HTML/AI Guardian outputs.
- AI hidden-content signal detection now includes pixel-level findings, not just container-level appended payloads.

## Improved
- OSINT Content Reader now promotes pixel-level hidden-content leads as visual cues and next actions.
- AI anomaly scoring now adds a technical review bump for strong pixel hidden-content leads.
- Report metrics count elevated pixel findings in hidden/content detections.
- AI Guardian OSINT card now shows pixel hidden-content cards with score, indicators, LSB strings, and channel notes.

## Analyst Notes
- Clean pixel scan results do not prove steganography is absent.
- LSB findings are strongest on PNG/BMP/lossless screenshots and weaker on JPEG.
- Decoded low-bit strings should be preserved separately from visible OCR text and manually validated before reporting.
