@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%src\modules\apps\runner.py" (
    set "ROOT_DIR=%SCRIPT_DIR:~0,-1%"
    set "APP_DIR=%SCRIPT_DIR%src"
) else if exist "%SCRIPT_DIR%modules\apps\runner.py" (
    for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
    set "APP_DIR=%SCRIPT_DIR%"
) else (
    echo ERROR: Could not find LifePIM runner module.
    exit /b 1
)

set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python.exe"

cd /d "%APP_DIR%"
"%PYTHON_EXE%" -m modules.apps.runner %*
