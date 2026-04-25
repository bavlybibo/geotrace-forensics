@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo [GeoTrace] Installing/checking PyInstaller...
python -m pip install pyinstaller >nul 2>nul
if errorlevel 1 (
  echo [GeoTrace] Failed to install or check PyInstaller.
  exit /b 1
)

echo [GeoTrace] Building production EXE without demo_evidence...
pyinstaller --noconfirm --clean geotrace_forensics_x.spec
if errorlevel 1 (
  echo [GeoTrace] Build failed.
  exit /b 1
)

echo.
echo [GeoTrace] Build complete. Check dist\GeoTraceForensicsX.
echo [GeoTrace] Run dist\GeoTraceForensicsX\GeoTraceForensicsX.exe and complete the release smoke test.
pause
