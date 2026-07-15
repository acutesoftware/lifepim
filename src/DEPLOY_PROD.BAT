@echo off
setlocal EnableExtensions

set "ROOT_DIR=D:\DATA_LLM\dev\lifepim-desktop"
set "PROD_DIR=C:\apps\LifePIM_Prod"
set "PROD_SRC=%PROD_DIR%\src"
set "PYTHON_EXE=%PROD_DIR%\.venv\Scripts\python.exe"
set "LIFEPIM_PORT=9741"

echo Deploying LifePIM to %PROD_DIR%

if not exist "%PROD_DIR%" mkdir "%PROD_DIR%"

if not exist "%ROOT_DIR%\src\app.py" (
  echo ERROR: Source tree not found at %ROOT_DIR%
  exit /b 1
)

echo Stopping any LifePIM listener on port %LIFEPIM_PORT%.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = Get-NetTCPConnection -LocalPort %LIFEPIM_PORT% -State Listen -ErrorAction SilentlyContinue; foreach ($p in $ports) { Stop-Process -Id $p.OwningProcess -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*run_waitress.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 exit /b %ERRORLEVEL%

robocopy "%ROOT_DIR%\src" "%PROD_DIR%\src" /MIR /FFT /R:2 /W:2 ^
  /XD "__pycache__" ".pytest_cache" "_codex_backup_*" ^
  /XF "*.db" "*.sqlite" "*.sqlite3" "*.duckdb" "*.db-shm" "*.db-wal" "*.sqlite-shm" "*.sqlite-wal" "*.log" "*.pyc" "*.pyo"
if errorlevel 8 exit /b %ERRORLEVEL%

robocopy "%ROOT_DIR%\scripts" "%PROD_DIR%\scripts" /MIR /FFT /R:2 /W:2 ^
  /XD "__pycache__" ".pytest_cache"
if errorlevel 8 exit /b %ERRORLEVEL%

copy /Y "%ROOT_DIR%\requirements.txt" "%PROD_DIR%\requirements.txt" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

copy /Y "%ROOT_DIR%\src\RUN_DESKTOP.BAT" "%PROD_DIR%\RUN_DESKTOP.BAT" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

copy /Y "%ROOT_DIR%\src\STOP_DESKTOP.BAT" "%PROD_DIR%\STOP_DESKTOP.BAT" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

if not exist "%PYTHON_EXE%" (
  echo Creating production virtual environment.
  py -3 -m venv "%PROD_DIR%\.venv"
  if errorlevel 1 exit /b %ERRORLEVEL%
)

echo Installing production requirements.
"%PYTHON_EXE%" -m pip install -r "%PROD_DIR%\requirements.txt"
if errorlevel 1 exit /b %ERRORLEVEL%

echo Compiling deployed Python files.
"%PYTHON_EXE%" -m compileall -q "%PROD_SRC%"
if errorlevel 1 exit /b %ERRORLEVEL%

if exist "C:\apps\caddy\Caddyfile" (
  findstr /C:"/api/pocket/v1/*" "C:\apps\caddy\Caddyfile" >nul
  if errorlevel 1 (
    echo WARNING: C:\apps\caddy\Caddyfile does not mention /api/pocket/v1/*.
    echo          Mobile HTTP sync may redirect to HTTPS until Caddy is updated.
  )
)

echo Starting production LifePIM.
start "LifePIM Desktop" /MIN "%PROD_DIR%\RUN_DESKTOP.BAT"

echo Waiting for health check.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(20); do { try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%LIFEPIM_PORT%/api/pocket/v1/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { Write-Host 'Health check OK:' $r.Content; exit 0 } } catch { Start-Sleep -Seconds 1 } } while ((Get-Date) -lt $deadline); Write-Host 'ERROR: Health check failed on http://127.0.0.1:%LIFEPIM_PORT%/api/pocket/v1/health'; exit 1"
if errorlevel 1 exit /b %ERRORLEVEL%

echo Deploy complete. Production is listening on port %LIFEPIM_PORT%.
exit /b 0
