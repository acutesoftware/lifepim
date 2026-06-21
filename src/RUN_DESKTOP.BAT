@echo off
setlocal

REM ============================================================
REM LifePIM Desktop Launcher
REM Works when this BAT is located in:
REM   <LifePIM root>\src\RUN_DESKTOP.BAT
REM and the venv is located at:
REM   <LifePIM root>\.venv\
REM ============================================================

REM note - to run this manually from a command line, use the line below
REM D:\DATA_LLM\dev\lifepim-desktop\.venv\Scripts\python.exe app.py
REM from the D:\DATA_LLM\dev\lifepim-desktop\src folder


REM Move to the LifePIM root folder, one level above /src
cd /d "%~dp0\.."

echo ============================================================
echo Starting LifePIM
echo Root folder: %CD%
echo ============================================================

set LIFEPIM_HOST=127.0.0.1
set LIFEPIM_PORT=9741
set LIFEPIM_DEBUG=false

if exist "%CD%\config\lifepim.local.toml" (
    set LIFEPIM_CONFIG=%CD%\config\lifepim.local.toml
    echo Using config: %LIFEPIM_CONFIG%
) else (
    echo No local config found at %CD%\config\lifepim.local.toml
)

if not exist "%CD%\.venv\Scripts\python.exe" (
    echo.
    echo ERROR: Python venv not found:
    echo   %CD%\.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

echo Python:
"%CD%\.venv\Scripts\python.exe" --version

echo.
echo Launching LifePIM server:
echo   http://%LIFEPIM_HOST%:%LIFEPIM_PORT%
echo.

REM Start Flask in a new command window
start "LifePIM Server" "%CD%\.venv\Scripts\python.exe" "%CD%\src\app.py"

REM Give Flask a few seconds to start
timeout /t 4 /nobreak > nul

REM Open browser
start "" "http://127.0.0.1:9741"

exit /b 0