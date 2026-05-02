@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo GeoTrace Optional Forensics Stack Installer
echo ============================================================
if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-forensics.txt
echo.
echo Optional forensic stack installed. Restart GeoTrace and open System Health.
echo For ExifTool binary fallback, place exiftool.exe under tools\bin\exiftool\exiftool.exe or set GEOTRACE_EXIFTOOL_CMD.
pause
