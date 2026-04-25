@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo [GeoTrace] Building DEMO EXE with demo_evidence included...
python -m pip install pyinstaller >nul 2>nul
if errorlevel 1 exit /b 1
pyinstaller --noconfirm --clean geotrace_forensics_x_demo.spec
if errorlevel 1 exit /b 1

echo.
echo [GeoTrace] Demo build complete. Do not publish this as the production release.
pause
