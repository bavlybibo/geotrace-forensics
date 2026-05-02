@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo GeoTrace - Optional AI Stack Setup
echo ============================================================
echo This is intentionally separate from the recommended setup.
echo It may download large packages and may fail on newer Python builds.
echo If it fails, GeoTrace still works with deterministic local analysis.
echo.

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

echo [1/2] Installing AI-lite foundations...
python -m pip install -r requirements-ai-lite.txt
if errorlevel 1 goto :error

echo [2/2] Installing full AI stack. This can take a long time...
python -m pip install -r requirements-ai.txt
if errorlevel 1 goto :softfail

echo.
echo [OPTIONAL] YOLO/Paddle pack is not installed automatically.
echo To install it later:
echo   .venv\Scripts\python.exe -m pip install -r requirements-ai-heavy.txt

echo.
python tools\check_optional_stack.py
pause
exit /b 0

:softfail
echo.
echo [WARN] Full AI stack did not install completely.
echo You can keep using GeoTrace. For normal forensic/geo work, use setup_recommended_stack_windows.bat.
python tools\check_optional_stack.py
pause
exit /b 0

:error
echo.
echo [ERROR] AI stack setup could not start.
pause
exit /b 1
