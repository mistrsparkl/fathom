@echo off
rem Runs an Imagination script (used by the right-click "Run with Imagination" menu).
cd /d "%~dp1"
py -3 "%~dp0imagination.py" "%~1"
rem Only wait when something went wrong, so the message can be read.
if errorlevel 1 pause
