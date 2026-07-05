@echo off
chcp 65001 >nul
rem AI Trading Assistant - headless Kiwoom sync (avoids AMD overlay crash)
cd /d "%~dp0"
echo [1/2] Kiwoom login + sync ...
".venv32\Scripts\python.exe" -m app.sync 20260601
echo.
set /p DEPLOY="Deploy to GitHub now? (Y/N): "
if /i "%DEPLOY%"=="Y" (
    echo [2/2] commit + push ...
    ".venv32\Scripts\python.exe" -m app.deploy
) else (
    echo Skipped deploy.
)
echo.
pause
