from __future__ import annotations
import subprocess
from dataclasses import dataclass, asdict
from .ocr_runtime import resolve_tesseract_binary

@dataclass(frozen=True)
class OCRDiagnostic:
    tesseract_path: str
    tesseract_installed: bool
    english_available: bool
    arabic_available: bool
    available_languages: list[str]
    status: str
    recommendation: str
    def to_dict(self)->dict: return asdict(self)
    def to_text(self)->str:
        langs=', '.join(self.available_languages[:12]) if self.available_languages else 'None detected'
        return f"Tesseract installed: {'Yes' if self.tesseract_installed else 'No'}\nPath: {self.tesseract_path or 'Not found'}\nEnglish language data: {'Yes' if self.english_available else 'No'}\nArabic language data: {'Yes' if self.arabic_available else 'No'}\nLanguages: {langs}\nOCR mode: {self.status}\nRecommendation: {self.recommendation}"

def run_ocr_diagnostic(timeout_seconds:int=4)->OCRDiagnostic:
    binary=resolve_tesseract_binary()
    if not binary:
        return OCRDiagnostic('', False, False, False, [], 'Disabled / fallback only', 'Install Tesseract OCR, add it to PATH or set GEOTRACE_TESSERACT_CMD, then install English + Arabic language packs.')
    try:
        r=subprocess.run([binary,'--list-langs'],capture_output=True,text=True,timeout=timeout_seconds)
        output=(r.stdout or '')+'\n'+(r.stderr or '')
        langs=[x.strip() for x in output.splitlines() if x.strip() and 'List of available languages' not in x]
    except Exception as exc:
        return OCRDiagnostic(binary, True, False, False, [], 'Installed but language check failed', f'Tesseract was found but could not be queried ({exc}). Verify PATH and tessdata.')
    eng=any(x=='eng' or x.startswith('eng') for x in langs); ara=any(x=='ara' or x.startswith('ara') for x in langs)
    if eng and ara: status,rec='Quick/Deep OCR ready','OCR stack is ready for English and Arabic screenshot/map/entity extraction.'
    elif eng: status,rec='English OCR ready / Arabic limited','Install Arabic tessdata (ara.traineddata) to improve Arabic map/entity extraction.'
    else: status,rec='Tesseract present / language data incomplete','Install eng and ara language data before depending on OCR in the final report.'
    return OCRDiagnostic(binary, True, eng, ara, langs, status, rec)
