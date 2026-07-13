@echo off
setlocal

set "ROOT_DIR=D:\DATA_LLM\dev\lifepim-desktop"
set "PROD_DIR=C:\apps\LifePIM_Prod"

echo Deploying LifePIM to %PROD_DIR%

if not exist "%PROD_DIR%" mkdir "%PROD_DIR%"

robocopy "%ROOT_DIR%\src" "%PROD_DIR%\src" /MIR /FFT /R:2 /W:2 ^
  /XD "__pycache__" ".pytest_cache" ^
  /XF "*.db" "*.sqlite" "*.sqlite3" "*.duckdb" "*.db-shm" "*.db-wal" "*.sqlite-shm" "*.sqlite-wal"
if errorlevel 8 exit /b %ERRORLEVEL%

robocopy "%ROOT_DIR%\scripts" "%PROD_DIR%\scripts" /MIR /FFT /R:2 /W:2 ^
  /XD "__pycache__" ".pytest_cache"
if errorlevel 8 exit /b %ERRORLEVEL%

copy /Y "%ROOT_DIR%\requirements.txt" "%PROD_DIR%\requirements.txt" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

echo Deploy complete.
exit /b 0
