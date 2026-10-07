@echo off
REM start.bat — Double-click launcher (calls the PowerShell script)
REM Run from the smart-farming-agent folder

echo Starting Smart Farming AI...
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
