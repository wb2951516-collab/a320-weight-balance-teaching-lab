@echo off
rem ===========================================================================
rem  IMPORTANT: keep this file ASCII-only.
rem  cmd.exe reads .cmd files using the OEM codepage (GBK on zh-CN Windows),
rem  NOT UTF-8. If Chinese text is written into this file it may be mis-decoded
rem  and break parsing. Therefore:
rem    - all messages below are ASCII
rem    - the folder path is obtained at runtime via %~dp0 (never hardcoded)
rem    - do NOT add "chcp 65001" before "cd /d %~dp0": switching the codepage
rem      mid-script can corrupt the (Chinese) path expansion
rem ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Preview Server - close this window to stop

set "PY=C:\Users\96258\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if not exist "index.html" (
  echo.
  echo   [ERROR] index.html not found in this folder.
  echo   Make sure this .cmd sits next to index.html.
  echo.
  pause
  exit /b 1
)

if not exist "teach_model.glb" (
  echo.
  echo   [WARN] teach_model.glb not found - the page will fail to load the model.
  echo.
)

rem ---- pick a free port: 8777 first, then up to 8786 ----
set "PORT="
for %%P in (8777 8778 8779 8780 8781 8782 8783 8784 8785 8786) do (
  if not defined PORT (
    powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue){exit 1}else{exit 0}" >nul 2>&1
    if not errorlevel 1 set "PORT=%%P"
  )
)
if not defined PORT set "PORT=8799"

echo.
echo   ============================================================
echo     Load-Balance Teaching  /  3D preview server
echo   ------------------------------------------------------------
echo     URL    : http://127.0.0.1:%PORT%/
echo     Folder : %CD%
echo     Stop   : close this window  (or press Ctrl+C)
echo   ------------------------------------------------------------
echo     Keep this window OPEN while using the page.
echo     Opening your browser in 2 seconds...
echo   ============================================================
echo.

rem ---- open the browser AFTER the server is up (2s delay, via python) ----
start "" /b "%PY%" -c "import time,webbrowser;time.sleep(2);webbrowser.open('http://127.0.0.1:%PORT%/')"

rem ---- run the server in the foreground so closing the window stops it ----
"%PY%" -m http.server %PORT% --bind 127.0.0.1
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo   [ERROR] Server exited with code %RC%.
  echo   Python tried: %PY%
  echo   If the port is busy, close other preview windows and retry.
) else (
  echo   Server stopped.
)
echo.
pause
