@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d %~dp0

set "GT_LOCAL_TEMP=%CD%\.temp"
if not exist "%GT_LOCAL_TEMP%" mkdir "%GT_LOCAL_TEMP%"
set "TEMP=%GT_LOCAL_TEMP%"
set "TMP=%GT_LOCAL_TEMP%"
set "PIP_CACHE_DIR=%GT_LOCAL_TEMP%\pip-cache"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_LAUNCH=py -3"
) else (
    set "PYTHON_LAUNCH=python"
)

echo [GeoTrace] Using temp dir: %GT_LOCAL_TEMP%
%PYTHON_LAUNCH% -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
    echo [GeoTrace] Python 3 was not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [GeoTrace] Creating local virtual environment...
    %PYTHON_LAUNCH% -m venv .venv
    if errorlevel 1 (
        echo [GeoTrace] Failed to create .venv. Check write permissions and Python installation.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [GeoTrace] .venv was not created correctly.
    pause
    exit /b 1
)

if not defined GEOTRACE_TESSERACT_CMD (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "GEOTRACE_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
)
if defined GEOTRACE_TESSERACT_CMD (
    echo [GeoTrace] Tesseract: %GEOTRACE_TESSERACT_CMD%
) else (
    echo [GeoTrace] Tesseract not found. OCR will fall back to visual map intelligence.
)

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

"%VENV_PYTHON%" -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo [GeoTrace] Dependency installation failed.
    echo [GeoTrace] Common fix: make sure %%LOCALAPPDATA%%\Temp exists, or keep using the bundled .temp folder created here.
    pause
    exit /b 1
)

"%VENV_PYTHON%" main.py
set "GT_EXIT=%ERRORLEVEL%"
if not "%GT_EXIT%"=="0" (
    echo [GeoTrace] App exited with code %GT_EXIT%.
)
pause
exit /b %GT_EXIT%
