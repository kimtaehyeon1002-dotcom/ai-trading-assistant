@echo off
chcp 65001 >nul
rem AI Trading Assistant - 무인(스케줄러) 동기화: 로그인→체결수집→빌드→자동 push
rem 사전 조건: 키움 OpenAPI AUTO 로그인 설정(트레이 아이콘 → 계좌비밀번호 저장 → AUTO 체크).
rem 로그인 창이 입력 대기로 방치되면 120초 후 실패 처리되고 로그에 남는다(무한 대기 방지).
rem 결과는 sync_auto.log 에 append — 문제 발생 시 이 파일부터 확인.
cd /d "%~dp0"
echo ===== %date% %time% sync start ===== >> sync_auto.log
".venv32\Scripts\python.exe" -m app.sync 20260601 --push >> sync_auto.log 2>&1
echo ===== %date% %time% sync end (exit %errorlevel%) ===== >> sync_auto.log
