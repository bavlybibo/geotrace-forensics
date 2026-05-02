@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if not exist VERSION (echo [GeoTrace] VERSION file missing & exit /b 1)
set /p GEOTRACE_VERSION=<VERSION

echo [GeoTrace] Cleaning runtime artifacts...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc >nul 2>nul
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist release rd /s /q release

if not exist .venv\Scripts\python.exe call setup_windows.bat
if errorlevel 1 exit /b 1

echo [GeoTrace] Installing release tooling...
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 exit /b 1

echo [GeoTrace] Audit gate...
.venv\Scripts\python.exe tools\audit_release.py
if errorlevel 1 exit /b 1

echo [GeoTrace] Compile gate...
.venv\Scripts\python.exe -m compileall -q app tests main.py
if errorlevel 1 exit /b 1

echo [GeoTrace] Test gate...
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 exit /b 1

echo [GeoTrace] Cleaning compiled test artifacts after validation...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc >nul 2>nul
if exist .pytest_cache rd /s /q .pytest_cache

echo [GeoTrace] Building EXE...
.venv\Scripts\pyinstaller.exe --noconfirm --clean geotrace_forensics_x.spec
if errorlevel 1 exit /b 1

echo [GeoTrace] Packaging release zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$name='GeoTrace_Forensics_X_v%GEOTRACE_VERSION%_Windows_x64'; New-Item -ItemType Directory -Force -Path release/$name | Out-Null; Copy-Item -Recurse -Force dist/GeoTraceForensicsX release/$name/GeoTraceForensicsX; Copy-Item README.md,LICENSE,PRIVACY.md,SECURITY.md,DISCLAIMER.md,THIRD_PARTY_NOTICES.md,RELEASE_CHECKLIST.md release/$name/; Compress-Archive -Path release/$name/* -DestinationPath release/$name.zip -Force; Get-FileHash release/$name.zip -Algorithm SHA256 | ForEach-Object { \"$($_.Hash)  $(Split-Path $_.Path -Leaf)\" } | Set-Content release/SHA256SUMS.txt"
if errorlevel 1 exit /b 1

echo.
echo [GeoTrace] Release package created under release\
exit /b 0
