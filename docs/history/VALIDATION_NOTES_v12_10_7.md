# v12.10.7 Validation Notes

Recommended manual validation flow:

1. Start a clean case and import one screenshot with no GPS.
2. Open **More → OCR Setup Wizard** and verify the displayed OCR status.
3. Select evidence and confirm Dashboard shows the image preview, Action Center, and Claim Links.
4. Run Manual Crop OCR on a visible label if Tesseract is available.
5. Generate Export Package.
6. Open Reports and confirm these artifacts are present:
   - Claim Matrix
   - Report Builder Index
   - Report Builder JSON
   - Package Verification
7. Run **Verify Last Package** and preserve `export_manifest.json` + `export_manifest.sha256`.
8. On Windows, build EXE and repeat the same flow from `dist/`.
