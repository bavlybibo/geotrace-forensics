@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [GeoTrace] Creating local virtual environment...
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 goto :error
)

echo [GeoTrace] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [GeoTrace] Installing core runtime dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [GeoTrace] Installing safe optional UI/Geo/OSINT stack...
.venv\Scripts\python.exe -m pip install -r requirements-ui.txt -r requirements-geo.txt -r requirements-osint.txt
if errorlevel 1 goto :error

echo [GeoTrace] Installing developer/release dependencies...
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

echo [GeoTrace] Running release smoke check...
.venv\Scripts\python.exe tools\smoke_check.py
if errorlevel 1 goto :error

echo.
echo [GeoTrace] Setup complete. Run run_windows.bat to start the app.
echo [GeoTrace] Heavy AI stack is optional. To install it, run setup_full_stack_windows.bat.
exit /b 0

:error
echo.
echo [GeoTrace] Setup failed. Check the error above.
exit /b 1
