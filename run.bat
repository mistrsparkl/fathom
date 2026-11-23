@echo off
rem Runs a Fathom script (used by the right-click "Run with Fathom" menu).
cd /d "%~dp1"
py -3 "%~dp0start.py" "%~1"
rem Only wait when something went wrong, so the message can be read.
if errorlevel 1 pause
