@echo off
echo Starting web server for LifePIM

start /min C:\Python36-32\python.exe web_app\web_lifepim.py
echo Server started - press SPACE to start browser
pause
start  http://127.0.0.1:5000