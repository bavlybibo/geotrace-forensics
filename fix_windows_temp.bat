@echo off
setlocal
set "GT_LOCAL_TEMP=%~dp0.temp"
if not exist "%GT_LOCAL_TEMP%" mkdir "%GT_LOCAL_TEMP%"
setx TEMP "%GT_LOCAL_TEMP%" >nul
setx TMP "%GT_LOCAL_TEMP%" >nul
echo TEMP and TMP now point to: %GT_LOCAL_TEMP%
echo Open a new terminal before retrying setup.
pause
