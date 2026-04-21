@echo off
setlocal
python -m pip install pyinstaller >nul 2>nul
pyinstaller --noconfirm --clean geotrace_forensics_x.spec
echo.
echo Build complete. Check the dist\GeoTraceForensicsX folder.
pause
