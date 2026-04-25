@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set APP_VERSION=12.9.2
set RELEASE_NAME=GeoTrace_Forensics_X_%APP_VERSION%_Windows_x64
set RELEASE_DIR=release\%RELEASE_NAME%

if not exist release mkdir release

echo [1/8] Cleaning cache/build/temp artifacts...
for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
for /r %%F in (*.pyc) do @if exist "%%F" del /f /q "%%F"
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .temp rmdir /s /q .temp
if exist report_assets rmdir /s /q report_assets
for /d /r %%D in (.pytest_cache) do @if exist "%%D" rmdir /s /q "%%D"
for /d /r %%D in (.ruff_cache) do @if exist "%%D" rmdir /s /q "%%D"
if exist release\staging rmdir /s /q release\staging

if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

echo [2/8] Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
python -m pip install pyinstaller
if errorlevel 1 exit /b 1

echo [3/8] Running compile check...
python -m compileall -q app tests main.py
if errorlevel 1 exit /b 1

echo [4/8] Running full pytest suite...
python -m pytest -q
if errorlevel 1 exit /b 1

echo [5/8] Building production EXE...
pyinstaller --noconfirm --clean geotrace_forensics_x.spec
if errorlevel 1 exit /b 1

echo [6/8] Copying release files...
if exist "dist\GeoTraceForensicsX\GeoTraceForensicsX.exe" (
    xcopy /E /I /Y "dist\GeoTraceForensicsX" "%RELEASE_DIR%\GeoTraceForensicsX" >nul
) else if exist "dist\GeoTraceForensicsX.exe" (
    mkdir "%RELEASE_DIR%\GeoTraceForensicsX"
    copy "dist\GeoTraceForensicsX.exe" "%RELEASE_DIR%\GeoTraceForensicsX\GeoTraceForensicsX.exe" >nul
) else (
    echo [GeoTrace] ERROR: PyInstaller output was not found.
    exit /b 1
)
if not exist "%RELEASE_DIR%\GeoTraceForensicsX\GeoTraceForensicsX.exe" (
    echo [GeoTrace] ERROR: Release EXE missing after copy.
    exit /b 1
)
copy README.md "%RELEASE_DIR%\README.md" >nul
copy LICENSE "%RELEASE_DIR%\LICENSE" >nul
copy PRIVACY.md "%RELEASE_DIR%\PRIVACY.md" >nul
copy SECURITY.md "%RELEASE_DIR%\SECURITY.md" >nul
copy DISCLAIMER.md "%RELEASE_DIR%\DISCLAIMER.md" >nul
copy THIRD_PARTY_NOTICES.md "%RELEASE_DIR%\THIRD_PARTY_NOTICES.md" >nul
copy RELEASE_CHECKLIST.md "%RELEASE_DIR%\RELEASE_CHECKLIST.md" >nul

echo [7/8] Creating ZIP package...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath 'release\%RELEASE_NAME%.zip' -Force"
if errorlevel 1 exit /b 1

echo [8/8] Writing SHA256SUMS.txt...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-FileHash 'release\%RELEASE_NAME%.zip' -Algorithm SHA256 | ForEach-Object { $_.Hash + '  ' + (Split-Path $_.Path -Leaf) } | Set-Content 'release\SHA256SUMS.txt'"
if errorlevel 1 exit /b 1

echo.
echo [GeoTrace] Release package created:
echo   release\%RELEASE_NAME%.zip
echo   release\SHA256SUMS.txt
echo.
echo [Manual gate] Now run the EXE from release\%RELEASE_NAME%\GeoTraceForensicsX and complete RELEASE_CHECKLIST.md.
exit /b 0
