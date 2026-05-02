@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo GeoTrace - Full Stack Setup ^(safe first, AI optional^)
echo ============================================================
echo Full stack now installs the recommended stack first and keeps
echo AI-heavy packages as a soft optional step, so the app is not
echo blocked by large model dependencies.
echo.

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 goto :error
  )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python -m pip install -r requirements-recommended.txt
if errorlevel 1 goto :error

if exist requirements-dev.txt (
  python -m pip install -r requirements-dev.txt
)

echo.
echo [OPTIONAL] Trying AI-lite first...
python -m pip install -r requirements-ai-lite.txt
if errorlevel 1 echo [WARN] AI-lite install failed; continuing because AI is optional.

echo.
echo [OPTIONAL] To install the full AI stack later, run:
echo   setup_ai_stack_windows.bat
echo.

python tools\check_optional_stack.py

echo.
echo [GeoTrace] Running smoke check...
python tools\smoke_check.py
if errorlevel 1 goto :error

echo.
echo [OK] Safe full setup completed. AI-heavy remains optional.
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed. Run setup_windows.bat for core-only install, then setup_recommended_stack_windows.bat.
pause
exit /b 1
