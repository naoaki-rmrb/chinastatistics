@echo off
REM Windows 用: このファイルをダブルクリックすると
REM 依存インストール → データ取得 → Excel生成 まで自動で行います。
REM 事前に「中国IPのVPN」をONにしておいてください。
setlocal
cd /d "%~dp0\.."
echo ==== 中国統計 Excel 生成（Windows） ====
echo ※ 中国IPのVPNがONになっているか確認してください。
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python が見つかりません。https://www.python.org からインストールしてください。
  echo インストール時に「Add Python to PATH」に必ずチェックを入れてください。
  pause
  exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat
echo 必要なライブラリを準備中...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

echo データを取得しています（初回は数分かかります）...
set PYTHONPATH=src
python -m chinastats.cli build
if errorlevel 1 (
  echo.
  echo 取得に失敗しました。VPN^(中国IP^)がONか確認して、もう一度お試しください。
) else (
  echo.
  echo 完了しました。Excel: output\china_indicators.xlsx
  start "" output
)
pause
