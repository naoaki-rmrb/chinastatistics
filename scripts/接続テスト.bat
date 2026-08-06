@echo off
chcp 65001 >nul
REM ダブルクリックで NBS への接続可否を確認します。
REM 事前に「中国IPのVPN」をONにしてください。
setlocal
cd /d "%~dp0\.."
echo === NBS 接続テスト ===
echo ※ 中国IPのVPNをONにしてから続けてください。
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python が見つかりません。https://www.python.org からインストールしてください。
  echo インストール時「Add Python to PATH」に必ずチェックを入れてください。
  pause
  exit /b 1
)

if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

set PYTHONPATH=src
python scripts\check_nbs.py
echo.
pause
