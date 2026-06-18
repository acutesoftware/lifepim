@echo off
setlocal

REM ============================================================
REM LifePIM Production Deploy
REM Mirrors the source code from:
REM   D:\DATA_LLM\dev\lifepim-desktop\src
REM to:
REM   C:\apps\LifePIM_Prod\src
REM
REM Database files are excluded so production data is not
REM overwritten or deleted during deployment.
REM ============================================================

set "SOURCE_DIR=D:\DATA_LLM\dev\lifepim-desktop\src"
set "DEST_DIR=C:\apps\LifePIM_Prod\src"

echo ============================================================
echo Deploying LifePIM source code
echo Source: %SOURCE_DIR%
echo Dest:   %DEST_DIR%
echo ============================================================
echo.

if not exist "%SOURCE_DIR%\" (
    echo ERROR: Source folder not found:
    echo   %SOURCE_DIR%
    echo.
    pause
    exit /b 1
)

if not exist "%DEST_DIR%\" (
    echo Creating destination folder:
    echo   %DEST_DIR%
    mkdir "%DEST_DIR%"
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create destination folder.
        pause
        exit /b 1
    )
)

echo Running robocopy...
echo.

robocopy "%SOURCE_DIR%" "%DEST_DIR%" /MIR /FFT /R:2 /W:2 ^
    /XD "__pycache__" ".pytest_cache" ^
    /XF "*.db" "*.sqlite" "*.sqlite3" "*.duckdb" "*.db-shm" "*.db-wal" "*.sqlite-shm" "*.sqlite-wal"

set "ROBOCOPY_EXIT=%ERRORLEVEL%"

echo.
if %ROBOCOPY_EXIT% GEQ 8 (
    echo ERROR: Robocopy failed with exit code %ROBOCOPY_EXIT%.
    echo.
    pause
    exit /b %ROBOCOPY_EXIT%
)

echo Deploy completed successfully. Robocopy exit code: %ROBOCOPY_EXIT%
echo.
pause
exit /b 0
