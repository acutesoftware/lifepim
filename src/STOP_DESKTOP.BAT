@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*run_waitress.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"