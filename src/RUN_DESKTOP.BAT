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
set "CADDY_CONFIG=%CADDY_DIR%\Caddyfile"
set "CADDY_DATA_DIR=%APPDATA%\Caddy"
set "CADDY_LOCAL_CA_DIR=%CADDY_DATA_DIR%\pki\authorities\local"

if /I "%LIFEPIM_ENV%"=="production" (
    if not exist "%CADDY_DATA_DIR%" (
        echo ERROR: Expected persistent Caddy data directory was not found:
        echo   %CADDY_DATA_DIR%
        echo Starting Caddy without the existing local CA would generate a new CA.
        echo Rebuilding LifePIM Pocket would then be required.
        exit /b 1
    )
    if not exist "%CADDY_LOCAL_CA_DIR%\root.crt" (
        echo ERROR: Expected Caddy local CA public root certificate was not found:
        echo   %CADDY_LOCAL_CA_DIR%\root.crt
        echo Starting Caddy without the existing local CA would generate a new CA.
        echo Rebuilding LifePIM Pocket would then be required.
        exit /b 1
    )
    if not exist "%CADDY_LOCAL_CA_DIR%\root.key" (
        echo ERROR: Expected Caddy local CA private key was not found:
        echo   %CADDY_LOCAL_CA_DIR%\root.key
        echo Do not copy this key into Android or Git. Restore it from the desktop backup before starting production.
        exit /b 1
    )
) else (
    if not exist "%CADDY_LOCAL_CA_DIR%\root.crt" (
        echo WARNING: Caddy local CA root certificate was not found at %CADDY_LOCAL_CA_DIR%\root.crt.
        echo WARNING: If Caddy generates a new CA, LifePIM Pocket must be rebuilt with the new public root certificate.
    )
)

if exist "%CADDY_EXE%" (
    if /I "%LIFEPIM_ENV%"=="production" (
        if not exist "%CADDY_CONFIG%" (
            echo ERROR: Caddy config not found at %CADDY_CONFIG%.
            echo Production startup requires Caddy in front of loopback-only Waitress.
            exit /b 1
        )
        if exist "%ROOT_DIR%\scripts\prod\update_caddy_lan_hosts.py" (
            "%PYTHON_EXE%" "%ROOT_DIR%\scripts\prod\update_caddy_lan_hosts.py" --config "%CADDY_CONFIG%" --upstream "127.0.0.1:%LIFEPIM_PORT%"
            if errorlevel 1 (
                echo ERROR: Could not update Caddy LAN host configuration.
                exit /b 1
            )
        )
        pushd "%CADDY_DIR%"
        "%CADDY_EXE%" validate --config "%CADDY_CONFIG%"
        if errorlevel 1 (
            popd
            echo ERROR: Caddy configuration validation failed. LifePIM was not started.
            exit /b 1
        )
        popd
    )
    tasklist /FI "IMAGENAME eq caddy_windows_amd64.exe" 2>NUL | find /I "caddy_windows_amd64.exe" >NUL
    if errorlevel 1 (
        echo Starting Caddy reverse proxy.
        pushd "%CADDY_DIR%"
        "%CADDY_EXE%" start --config "%CADDY_CONFIG%"
        if errorlevel 1 (
            popd
            if /I "%LIFEPIM_ENV%"=="production" (
                echo ERROR: Caddy did not start cleanly. LifePIM was not started.
                exit /b 1
            )
            echo WARNING: Caddy did not start cleanly. Development startup will continue on Waitress.
        ) else (
            popd
        )
    ) else (
        echo Caddy reverse proxy is already running.
    )
) else (
    if /I "%LIFEPIM_ENV%"=="production" (
        echo ERROR: Caddy was not found at %CADDY_EXE%.
        echo Production startup requires Caddy in front of loopback-only Waitress.
        exit /b 1
    )
    echo WARNING: Caddy was not found at %CADDY_EXE%.
    echo Development startup will continue on Waitress without HTTPS reverse proxy startup.
)

cd /d "%APP_DIR%"
echo Starting LifePIM with Waitress on http://%LIFEPIM_HOST%:%LIFEPIM_PORT%
"%PYTHON_EXE%" run_waitress.py
