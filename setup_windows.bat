@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d %~dp0

set "GT_LOCAL_TEMP=%CD%\\.temp"
if not exist "%GT_LOCAL_TEMP%" mkdir "%GT_LOCAL_TEMP%"
set "TEMP=%GT_LOCAL_TEMP%"
set "TMP=%GT_LOCAL_TEMP%"
set "PIP_CACHE_DIR=%GT_LOCAL_TEMP%\\pip-cache"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_LAUNCH=py -3"
) else (
    set "PYTHON_LAUNCH=python"
)

%PYTHON_LAUNCH% -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
    echo [GeoTrace] Python 3 was not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

if not exist ".venv\\Scripts\\python.exe" (
    echo [GeoTrace] Creating local virtual environment...
    %PYTHON_LAUNCH% -m venv .venv
    if errorlevel 1 (
        echo [GeoTrace] Failed to create .venv.
        pause
        exit /b 1
    )
)

call ".venv\\Scripts\\activate.bat"
if errorlevel 1 (
    echo [GeoTrace] Failed to activate .venv.
    pause
    exit /b 1
)

python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo [GeoTrace] Dependency installation failed.
    pause
    exit /b 1
)

echo [GeoTrace] Generating demo evidence...
python tools\generate_demo_evidence.py
if errorlevel 1 (
    echo [GeoTrace] Demo evidence generation hit a non-fatal issue. The app can still run.
)

echo [GeoTrace] Setup finished.
pause
