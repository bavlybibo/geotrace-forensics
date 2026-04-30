from __future__ import annotations

"""OCR setup wizard backend.

No installer is launched automatically.  The helper gives analysts a deterministic
status, environment variable guidance, and a Windows-ready checklist that can be
shown in the UI or exported into diagnostics.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import os

from .ocr_diagnostics import OCRDiagnostic, run_ocr_diagnostic


@dataclass(slots=True)
class OCRSetupStatus:
    ready: bool
    severity: str
    diagnostic: dict
    checklist: list[str]
    windows_commands: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        diag = OCRDiagnostic(**self.diagnostic).to_text() if self.diagnostic else "Diagnostic unavailable."
        lines = ["GeoTrace OCR Setup Wizard", "==========================", f"Ready: {'Yes' if self.ready else 'No'}", f"Severity: {self.severity}", "", diag, "", "Checklist:"]
        lines.extend(f"- {item}" for item in self.checklist)
        lines.extend(["", "Windows commands / environment hints:"])
        lines.extend(f"- {item}" for item in self.windows_commands)
        if self.notes:
            lines.extend(["", "Notes:"])
            lines.extend(f"- {item}" for item in self.notes)
        return "\n".join(lines).strip() + "\n"


def build_ocr_setup_status() -> OCRSetupStatus:
    diag = run_ocr_diagnostic()
    ready = bool(diag.tesseract_installed and diag.english_available)
    bilingual_ready = bool(diag.english_available and diag.arabic_available)
    if bilingual_ready:
        severity = "ready"
    elif ready:
        severity = "limited_arabic"
    elif diag.tesseract_installed:
        severity = "language_data_missing"
    else:
        severity = "disabled"

    checklist = [
        "Install Tesseract OCR and keep it local/offline.",
        "Install eng.traineddata for English/Latin screenshots.",
        "Install ara.traineddata for Arabic map labels and mixed Arabic/English screenshots.",
        "Add tesseract.exe to PATH or set GEOTRACE_TESSERACT_CMD to the exact executable path.",
        "Restart GeoTrace, then run Deep Map OCR or Manual Crop OCR on a selected evidence item.",
    ]
    commands = [
        r'setx GEOTRACE_TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"',
        r'"C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs',
        "PowerShell: $env:GEOTRACE_OCR_MODE='map_deep' before launching the app for map-heavy cases.",
    ]
    notes = []
    env_path = os.getenv("GEOTRACE_TESSERACT_CMD") or os.getenv("TESSERACT_CMD")
    if env_path:
        notes.append(f"Environment override detected: {env_path}")
        if not Path(env_path).exists():
            notes.append("The configured OCR executable path does not currently exist on disk.")
    if not diag.tesseract_installed:
        notes.append("OCR-dependent features will fall back to visual heuristics only until Tesseract is available.")
    elif not diag.english_available:
        notes.append("Tesseract is present, but English language data is missing; OCR reliability will be very low.")
    elif not diag.arabic_available:
        notes.append("Arabic labels may be missed until ara.traineddata is installed.")
    else:
        notes.append("OCR stack is ready for Quick, Deep, Map Deep, and Manual Crop OCR modes.")
    return OCRSetupStatus(ready=ready, severity=severity, diagnostic=diag.to_dict(), checklist=checklist, windows_commands=commands, notes=notes)
