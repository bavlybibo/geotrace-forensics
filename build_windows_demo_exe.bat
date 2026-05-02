@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call setup_windows.bat
if errorlevel 1 exit /b 1
.venv\Scripts\pyinstaller.exe --noconfirm --clean geotrace_forensics_x_demo.spec
