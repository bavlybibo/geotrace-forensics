# Current Stack Status Explained

Your shown status is healthy for the core app:

- Required dependencies: `5/5 OK`
- Application ready: `YES`
- Optional dependencies: partially installed only
- GeoNames big city index: not imported yet
- Local vision model: not configured
- Online map/OSINT: disabled by default for privacy

The important fix is not code-breaking. It is setup order:

1. Install recommended optional stack.
2. Put GeoNames data in `data\geo\raw`.
3. Run `import_project_geo_data.bat`.
4. Install Tesseract/ExifTool binaries only if you need deep OCR/metadata.
5. Install AI-heavy packages last.

GeoTrace already separates native GPS, derived map/OCR coordinates, and map search leads correctly. A screenshot-derived coordinate must stay as a lead unless native EXIF GPS or another source corroborates it.
