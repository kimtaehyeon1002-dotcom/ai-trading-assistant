@echo off
rem AI Trading Assistant desktop app (32-bit venv required for Kiwoom OCX)
cd /d "%~dp0"
".venv32\Scripts\python.exe" -m app.main
pause
