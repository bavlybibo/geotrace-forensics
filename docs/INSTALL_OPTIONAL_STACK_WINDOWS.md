# GeoTrace Optional Stack Setup — Windows

GeoTrace can run with the required core dependencies only. The optional stack improves UI, geo matching, metadata extraction, QR/barcode detection, and local AI experiments.

## What your current health output means

`Application ready: YES` means the app can start and the required runtime is installed.

`Optional: 7/30` means most optional engines are not installed yet. This is not a crash; it only means features such as ExifTool, QR detection, RapidFuzz geo matching, YOLO, EasyOCR, and PaddleOCR are not active.

## Recommended install order

From the project folder:

```bat
setup_recommended_stack_windows.bat
```

This installs the safe useful stack:

- QtAwesome and PyQtGraph for UI polish and charts
- RapidFuzz, geopy, shapely, and h3 for geo confidence and fuzzy matching
- PyExifTool, zxing-cpp, ImageHash, timezonefinder, pycountry, and DuckDB for deeper forensics and geo indexing
- requests-cache for privacy-gated OSINT caching

## AI stack

Use AI-heavy packages only after the recommended stack is clean:

```bat
setup_ai_stack_windows.bat
```

The AI stack is optional and may download large dependencies. If it fails, the normal app still works.

## GeoNames data

Put one of these files inside:

```text
data\geo\raw\cities1000.zip
data\geo\raw\cities5000.zip
data\geo\raw\cities15000.zip
data\geo\raw\allCountries.zip
```

Then run:

```bat
import_project_geo_data.bat
```

The generated file should appear here:

```text
data\osint\generated_geocoder_index.json
```

For stronger Arabic/English matching, also place these optional files in `data\geo\raw`:

```text
alternateNamesV2.zip
countryInfo.txt
admin1CodesASCII.txt
admin2Codes.txt
timeZones.txt
```

## External binaries

Tesseract OCR and ExifTool are external programs, not just Python packages.

- Tesseract: install it and add it to PATH, or keep OCR mode quick/off.
- ExifTool: put `exiftool.exe` at `tools\bin\exiftool\exiftool.exe`, or set `GEOTRACE_EXIFTOOL_CMD`.
