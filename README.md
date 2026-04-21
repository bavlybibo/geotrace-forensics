<p align="center">
  <img src="assets/app_icon.png" width="128" alt="GeoTrace Forensics X logo">
</p>

<h1 align="center">GeoTrace Forensics X</h1>

<p align="center">
  <strong>A premium desktop digital-forensics command center for image intelligence, metadata recovery, timestamp reconstruction, GPS correlation, duplicate analysis, chain of custody, and analyst-ready reporting.</strong>
</p>

<p align="center">
  <em>Acquire → Verify → Extract → Correlate → Score → Report</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.x-09111f?style=for-the-badge&logo=python&logoColor=7dd3fc">
  <img alt="Desktop" src="https://img.shields.io/badge/Desktop-PyQt5-09111f?style=for-the-badge&logo=qt&logoColor=7dd3fc">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Windows%20First-09111f?style=for-the-badge&logo=windows&logoColor=7dd3fc">
  <img alt="Reports" src="https://img.shields.io/badge/Exports-HTML%20%7C%20PDF%20%7C%20CSV%20%7C%20JSON-09111f?style=for-the-badge&logo=files&logoColor=7dd3fc">
</p>

<p align="center">
  <a href="#visual-tour">Visual Tour</a> •
  <a href="#core-capabilities">Capabilities</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#project-structure">Structure</a> •
  <a href="#demo-flow">Demo Flow</a>
</p>

<p align="center">
  <img alt="GeoTrace splash screen" src="assets/splash.png" width="100%">
</p>

---

## Overview

**GeoTrace Forensics X** is a case-oriented desktop workspace for investigating image-based evidence with a practical forensic workflow and a presentation-ready interface.

It is designed to help analysts move from raw files to structured conclusions through six clear stages:

- **Acquire** evidence into an isolated case
- **Verify** integrity with hashes and custody events
- **Extract** metadata, timestamps, and structural clues
- **Correlate** devices, locations, duplicates, and time signals
- **Score** findings with contextual risk and confidence
- **Report** the result in a clean export package

Instead of behaving like a simple EXIF viewer, GeoTrace is positioned as a **forensics command center** for image intelligence.

---

## Why This Project Stands Out

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>Context-aware logic</h3>
      <p>Missing EXIF is not blindly treated as suspicious. Screenshots, edited media, chat exports, and camera photos are interpreted with different expectations.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Risk + confidence together</h3>
      <p>Each record can be judged not only by risk, but also by how strong the conclusion is, which makes analyst explanations more mature and credible.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>Duplicate intelligence</h3>
      <p>GeoTrace combines exact hashing and perceptual similarity so repeated or recompressed evidence can still be linked.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Report-first workflow</h3>
      <p>The application is built to end with a real deliverable: HTML, PDF, CSV, and JSON outputs ready for demos, coursework, and investigation summaries.</p>
    </td>
  </tr>
</table>

---

## Visual Tour

<p align="center">
  <img alt="Investigation pipeline" src="docs/readme/forensic-pipeline.svg" width="100%">
</p>

<p align="center">
  <img alt="Command center map" src="docs/readme/command-center-map.svg" width="100%">
</p>

<p align="center">
  <img alt="Demo evidence gallery" src="docs/readme/demo-gallery.png" width="100%">
</p>

<p align="center">
  <img alt="Export package diagram" src="docs/readme/export-package.svg" width="100%">
</p>

> Recommended: replace the gallery later with real in-app screenshots from your final build for an even stronger GitHub first impression.

---

## Core Capabilities

### 1) Metadata Intelligence

GeoTrace extracts and correlates a broad range of evidence signals, including:

- EXIF camera and device tags
- software and editor tags
- lens, ISO, exposure, focal length
- format, DPI, alpha channel, and color mode
- filesystem timestamps
- filename-based time recovery
- GPS coordinates and altitude when available
- structural and source hints for screenshots and exports

### 2) Timestamp Recovery

The tool does not rely on one timestamp source only. It can recover time context from multiple candidates such as:

- EXIF date and time fields
- filename patterns
- filesystem timestamps
- exported-media naming styles
- screenshot-oriented hints when recoverable

This makes the workflow more useful for evidence that has been forwarded, renamed, stripped, exported, or edited.

### 3) GPS Correlation

When location data exists, GeoTrace helps the analyst review:

- latitude and longitude
- altitude
- map-oriented context
- geo investigation leads
- consistency between location-related clues

### 4) Duplicate and Similarity Analysis

GeoTrace supports two complementary approaches:

- **cryptographic hashing** for exact integrity checks
- **perceptual hashing** for visually similar or recompressed copies

This makes duplicate review stronger than plain byte-for-byte matching.

### 5) Chain of Custody

The case workflow includes integrity-oriented event logging with a visible audit trail, helping document:

- intake events
- analyst notes
- evidence actions
- hash-linked traceability
- validation during reporting

### 6) Analyst-Ready Reporting

A single case can generate a reporting package that may include:

- HTML report
- PDF report
- CSV evidence summary
- JSON evidence summary
- executive-style summary outputs
- validation-oriented package manifests

---

## Command Center Modules

| Module | What the analyst gets |
|---|---|
| **Dashboard** | Case health, evidence counts, GPS coverage, duplicate coverage, and high-level investigation KPIs |
| **Review** | Preview-first evidence triage and record-by-record inspection |
| **Metadata** | EXIF, device, editor, format, and filesystem context |
| **Timeline** | Recovered time candidates, chronology support, and timestamp conflict review |
| **Geo / OSINT Leads** | GPS signals, map clues, coordinates, and follow-up location leads |
| **Compare** | Side-by-side review of related or near-duplicate items |
| **Audit** | Chain of custody, event history, and analyst notes |
| **Insights** | Charts for source types, risk distribution, GPS coverage, and duplicate clusters |

---

## Investigation Methodology

GeoTrace follows a practical digital-forensics process:

### Acquire
Import one image or a full folder into an isolated case.

### Verify
Compute hashes and register intake events.

### Extract
Recover metadata, timestamps, filesystem context, and structural clues.

### Correlate
Connect time signals, source type, GPS, and duplicate relationships.

### Score
Assign context-aware risk and confidence indicators.

### Report
Export a presentation-ready package for analyst review.

---

## Demo Flow

For a strong live demo, project presentation, or judging session:

1. Import a folder from `demo_evidence/`
2. Show the dashboard and explain coverage metrics
3. Open a screenshot and explain why missing EXIF is not always suspicious
4. Open a camera-style image and walk through the metadata panel
5. Show the timeline view and recovered time candidates
6. Show duplicate clustering with a repeated or recompressed image pair
7. Open the geo lead when GPS or map clues exist
8. Generate the export package and open the final reports

---

## Quick Start

### Windows

```powershell
python -m pip install -r requirements.txt
python main.py
```

Or use the included batch files:

- `setup_windows.bat`
- `run_windows.bat`

### Build a Windows Executable

```powershell
py -m pip install pyinstaller
build_windows_exe.bat
```

---

## Supported Formats

- JPG / JPEG
- PNG
- TIFF / TIF
- WEBP
- BMP
- GIF
- HEIC / HEIF *(via `pillow-heif`)*

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New case |
| `Ctrl+O` | Import files |
| `Ctrl+Shift+O` | Import folder |
| `Ctrl+R` | Generate reports |
| `Ctrl+F` | Focus search |
| `Ctrl+S` | Save notes |
| `Ctrl+,` | Open settings |
| `Ctrl+Shift+C` | Compare mode |
| `Ctrl+Shift+D` | Duplicate review |
| `Ctrl+1..7` | Switch pages |

---

## Project Structure

```text
GeoTrace Forensics X/
├─ app/
│  ├─ core/
│  │  ├─ anomalies.py
│  │  ├─ case_db.py
│  │  ├─ case_manager.py
│  │  ├─ exif_service.py
│  │  ├─ explainability.py
│  │  ├─ gps_utils.py
│  │  ├─ hashing.py
│  │  ├─ map_service.py
│  │  ├─ models.py
│  │  ├─ report_service.py
│  │  ├─ validation_service.py
│  │  └─ visual_clues.py
│  └─ ui/
│     ├─ dialogs.py
│     ├─ main_window.py
│     ├─ styles.py
│     └─ widgets.py
├─ assets/
│  ├─ app_icon.png
│  └─ splash.png
├─ demo_evidence/
├─ docs/readme/
├─ tools/
├─ tests/
├─ main.py
└─ requirements.txt
```

---

## Windows Notes

- `setup_windows.bat` and `run_windows.bat` are used for streamlined local setup.
- OCR support is optional. If your build depends on it, install **Tesseract OCR** and make sure it is available on system PATH.
- If OCR is unavailable, the application should still degrade gracefully instead of failing silently.

If Windows reports a TEMP or TMP issue, run:

```powershell
fix_windows_temp.bat
```

Then open a new terminal and run setup again.

---

## Design Philosophy

This project intentionally separates **structural validation** from **origin certainty**.

That means:

- **Verified** does not automatically prove legal authenticity or provenance
- **Partial** can still be useful evidence with limited parser support
- **Review Required** means the analyst should inspect and corroborate the record manually

This makes the project more realistic for digital-forensics teaching, demos, and case workflows.

---

## Roadmap

Strong next upgrades for the repository could include:

- real UI screenshots in the README gallery
- richer geo intelligence and stronger map enrichment
- a deeper evidence comparison workspace
- explainability cards for scoring decisions
- case templates for different investigation scenarios
- plugin-style import and export extensions

---

## Ideal Use Cases

GeoTrace Forensics X is well-suited for:

- digital forensics coursework
- graduation project demonstrations
- media evidence review
- timestamp reconstruction exercises
- duplicate discovery workflows
- GPS-based media correlation
- analyst report generation

---

## License

Add your preferred license here.

Example:

```text
MIT License
```

---

## Author / Team

Add your name, team, course, or project attribution here.
