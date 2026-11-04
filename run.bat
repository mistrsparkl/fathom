@echo off
rem Runs an Imagination script (used by the right-click "Run with Imagination" menu).
cd /d "%~dp1"
py -3 "%~dp0imagination.py" "%~1"
echo.
pause
