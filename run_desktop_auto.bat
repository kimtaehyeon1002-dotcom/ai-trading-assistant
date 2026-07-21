@echo off
chcp 65001 >nul
rem AI Trading Assistant - unattended sync for Task Scheduler (login -> sync -> build -> push)
rem Prerequisite: Kiwoom OpenAPI AUTO login (tray icon -> save account password -> check AUTO).
rem If the login window sits waiting for input (AUTO not set / version update popup),
rem it fails after 120s instead of hanging forever. Check sync_auto.log on any problem.
rem NOTE: comments in this file must stay ASCII-only - cmd parses batch files with the
rem system codepage (CP949) and UTF-8 Korean bytes break line parsing into bogus commands.
cd /d "%~dp0"
echo ===== %date% %time% sync start ===== >> sync_auto.log
".venv32\Scripts\python.exe" -m app.sync 20260601 --push >> sync_auto.log 2>&1
echo ===== %date% %time% sync end (exit %errorlevel%) ===== >> sync_auto.log
