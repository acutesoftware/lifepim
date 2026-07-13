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

if /I "%LIFEPIM_ENV%"=="production" if not defined LIFEPIM_SECRET_KEY (
    echo ERROR: LIFEPIM_SECRET_KEY is not set.
    echo Set a persistent secret before starting production, for example:
    echo   setx LIFEPIM_SECRET_KEY "replace-with-a-long-random-secret"
    exit /b 1
)

set "CADDY_DIR=C:\apps\caddy"
set "CADDY_EXE=%CADDY_DIR%\caddy_windows_amd64.exe"

if exist "%CADDY_EXE%" (
    tasklist /FI "IMAGENAME eq caddy_windows_amd64.exe" 2>NUL | find /I "caddy_windows_amd64.exe" >NUL
    if errorlevel 1 (
        echo Starting Caddy reverse proxy.
        pushd "%CADDY_DIR%"
        "%CADDY_EXE%" start
        if errorlevel 1 (
            popd
            echo WARNING: Caddy did not start cleanly. LifePIM will still start on Waitress.
        ) else (
            popd
        )
    ) else (
        echo Caddy reverse proxy is already running.
    )
) else (
    echo WARNING: Caddy was not found at %CADDY_EXE%.
    echo LifePIM will still start on Waitress without HTTPS reverse proxy startup.
)

cd /d "%APP_DIR%"
echo Starting LifePIM with Waitress on http://%LIFEPIM_HOST%:%LIFEPIM_PORT%
"%PYTHON_EXE%" run_waitress.py
