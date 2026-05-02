@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo GeoTrace - Recommended Optional Stack Setup
echo ============================================================
echo This installs UI polish, geo intelligence, forensic helpers,
echo and privacy-gated OSINT helpers. It does NOT install the huge
echo AI-heavy packages like EasyOCR, OpenCLIP, YOLO, or PaddleOCR.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] .venv not found. Creating it with the default Python...
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 goto :error
  )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

python -m pip install -r requirements-recommended.txt
if errorlevel 1 goto :error

echo.
echo [GeoTrace] Optional stack status:
python tools\check_optional_stack.py

echo.
echo [GeoTrace] Dependency health:
python -c "from app.core.dependency_check import run_dependency_check; print(run_dependency_check('.').to_text())"

echo.
echo [OK] Recommended optional stack installed.
echo Next: put cities1000.zip or cities15000.zip in data\geo\raw and run import_project_geo_data.bat
pause
exit /b 0

:error
echo.
echo [ERROR] Recommended optional stack setup failed.
echo Try running these manually inside the project folder:
echo   .venv\Scripts\python.exe -m pip install -r requirements-ui.txt
echo   .venv\Scripts\python.exe -m pip install -r requirements-geo.txt
echo   .venv\Scripts\python.exe -m pip install -r requirements-forensics.txt
echo   .venv\Scripts\python.exe -m pip install -r requirements-osint.txt
pause
exit /b 1
