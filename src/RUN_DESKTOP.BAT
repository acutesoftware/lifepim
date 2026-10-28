@echo off
setlocal

REM LifePIM production launcher.
REM Works from either:
REM   C:\apps\LifePIM_Prod\RUN_DESKTOP.BAT
REM   C:\apps\LifePIM_Prod\src\RUN_DESKTOP.BAT

set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%app.py" (
    set "APP_DIR=%SCRIPT_DIR%"
    for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
) else if exist "%SCRIPT_DIR%src\app.py" (
    set "ROOT_DIR=%SCRIPT_DIR:~0,-1%"
    set "APP_DIR=%SCRIPT_DIR%src"
) else (
    echo ERROR: Could not find app.py next to this file or in .\src.
    exit /b 1
)

set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: Python virtual environment not found:
    echo   %PYTHON_EXE%
    exit /b 1
)

if not defined LIFEPIM_ENV set "LIFEPIM_ENV=production"
if not defined LIFEPIM_HOST set "LIFEPIM_HOST=127.0.0.1"
if not defined LIFEPIM_PORT set "LIFEPIM_PORT=9741"

if /I not "%LIFEPIM_HOST%"=="127.0.0.1" if /I not "%LIFEPIM_HOST%"=="localhost" if /I not "%LIFEPIM_HOST%"=="::1" (
    echo ERROR: LifePIM Desktop is local-only.
    echo LIFEPIM_HOST must be 127.0.0.1, localhost, or ::1; received "%LIFEPIM_HOST%".
    exit /b 1
)

if /I "%LIFEPIM_ENV%"=="production" if not defined LIFEPIM_SECRET_KEY (
    echo ERROR: LIFEPIM_SECRET_KEY is not set.
    echo Set a persistent secret before starting production, for example:
    echo   setx LIFEPIM_SECRET_KEY "replace-with-a-long-random-secret"
    exit /b 1
)

cd /d "%APP_DIR%"
echo Starting LifePIM with Waitress on http://%LIFEPIM_HOST%:%LIFEPIM_PORT%
"%PYTHON_EXE%" run_waitress.py
