@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo GeoTrace - Build in-project offline geocoder index
echo ============================================================
echo.
if not exist "data\geo\raw" mkdir "data\geo\raw"
if not exist "data\geo\processed" mkdir "data\geo\processed"
if not exist "data\osint" mkdir "data\osint"

set HAS_GEO=0
if exist "data\geo\raw\cities1000.zip" set HAS_GEO=1
if exist "data\geo\raw\cities1000.txt" set HAS_GEO=1
if exist "data\geo\raw\cities5000.zip" set HAS_GEO=1
if exist "data\geo\raw\cities5000.txt" set HAS_GEO=1
if exist "data\geo\raw\cities15000.zip" set HAS_GEO=1
if exist "data\geo\raw\cities15000.txt" set HAS_GEO=1
if exist "data\geo\raw\allCountries.zip" set HAS_GEO=1
if exist "data\geo\raw\allCountries.txt" set HAS_GEO=1
if exist "data\geo\processed\places_geonames.json" set HAS_GEO=1

if "%HAS_GEO%"=="0" (
  echo [INFO] Put one primary city/place source first:
  echo        data\geo\raw\cities1000.zip      ^(recommended for wide coverage^)
  echo        data\geo\raw\cities5000.zip
  echo        data\geo\raw\cities15000.zip
  echo        data\geo\raw\allCountries.zip    ^(large; filtered by importer^)
  echo        data\geo\processed\places_geonames.json
  echo.
  echo Optional enrichment files:
  echo        data\geo\raw\alternateNamesV2.zip
  echo        data\geo\raw\countryInfo.txt
  echo        data\geo\raw\admin1CodesASCII.txt
  echo        data\geo\raw\admin2Codes.txt
  echo        data\geo\raw\timeZones.txt
  echo.
  echo The importer can read GeoNames TXT/ZIP, CSV, TSV, JSON, JSONL, NDJSON, and GeoJSON.
  echo.
)

if exist ".venv\Scripts\python.exe" (
  set PYTHON_EXE=.venv\Scripts\python.exe
) else (
  set PYTHON_EXE=python
)

%PYTHON_EXE% tools\build_offline_geocoder_index.py
if errorlevel 1 (
  echo.
  echo [ERROR] Import failed. Check Python and the file path/format.
  pause
  exit /b 1
)
echo.
echo [OK] Generated data\osint\generated_geocoder_index.json
echo GeoTrace will load it automatically on next scan.
echo.
echo Tip: cities1000.zip + alternateNamesV2.zip gives the best Arabic/English city alias coverage.
pause
