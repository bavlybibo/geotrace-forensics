# Optional Forensics + Heavy AI Stack

GeoTrace remains offline-first and safe by default. The optional engines below only
activate when installed/configured, and missing packages never block normal startup.

## Forensics stack

Install:

```bat
setup_forensics_stack_windows.bat
```

or:

```bat
pip install -r requirements-forensics.txt
```

Adds:

- **ExifTool bridge**: deeper EXIF/XMP/IPTC/MakerNotes extraction via local `exiftool`.
- **QR/barcode detector**: `zxing-cpp` first, `pyzbar` fallback.
- **ImageHash profile**: average/perceptual/difference/wavelet hashes for duplicate/tamper triage.
- **timezonefinder**: offline timezone lookup from native or derived coordinates.
- **pycountry**: ISO country normalization helpers.
- **DuckDB**: future large GeoNames/local-index acceleration.

## ExifTool binary

GeoTrace looks for ExifTool in this order:

1. `GEOTRACE_EXIFTOOL_CMD`
2. `tools\bin\exiftool\exiftool.exe`
3. `exiftool` / `exiftool.exe` on PATH

The bridge runs with `shell=False`, a bounded timeout, and local-only metadata parsing.

## Heavy AI stack

Install only on capable machines:

```bat
pip install -r requirements-ai-heavy.txt
```

YOLO object detection is disabled by default. Enable deliberately:

```bat
set GEOTRACE_YOLO_ENABLED=1
set GEOTRACE_YOLO_MODEL=C:\path\to\yolov8n.pt
```

GeoTrace will not load YOLO unless both variables are configured. This avoids
accidental downloads, freezes, and overclaiming model output as forensic proof.

## UI integration

Open **System Health** to see:

- required vs optional dependency status
- ExifTool binary status
- QR/barcode detector readiness
- YOLO/PaddleOCR readiness
- truth-status guidance for what is real vs optional

Deep Image Intelligence now includes optional barcode, ImageHash, and YOLO metrics
when those engines are installed/enabled.
