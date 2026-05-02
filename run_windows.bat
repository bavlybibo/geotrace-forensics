@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo [GeoTrace] .venv was not found. Running setup first...
  call setup_windows.bat
  if errorlevel 1 exit /b 1
)

if "%GEOTRACE_OCR_MODE%"=="" set GEOTRACE_OCR_MODE=quick
if "%GEOTRACE_OCR_TIMEOUT%"=="" set GEOTRACE_OCR_TIMEOUT=0.8
if "%GEOTRACE_OCR_GLOBAL_TIMEOUT%"=="" set GEOTRACE_OCR_GLOBAL_TIMEOUT=5.0
if "%GEOTRACE_OCR_MAX_CALLS%"=="" set GEOTRACE_OCR_MAX_CALLS=4
if "%GEOTRACE_LOG_PRIVACY%"=="" set GEOTRACE_LOG_PRIVACY=redacted

echo [GeoTrace] Starting GeoTrace Forensics X...
.venv\Scripts\python.exe main.py
