@echo off
chcp 65001 >nul
REM ダブルクリックで NBS への接続可否を確認します。
REM 事前に「中国IPのVPN」をONにしてください。
REM 結果は「接続テスト結果.txt」にも保存されます。
setlocal enabledelayedexpansion
cd /d "%~dp0\.."
set "LOG=%CD%\接続テスト結果.txt"

echo ================================================= > "%LOG%"
echo  NBS 接続テスト 結果 >> "%LOG%"
echo  日時: %date% %time% >> "%LOG%"
echo ================================================= >> "%LOG%"

echo === NBS 接続テスト ===
echo ※ 中国IPのVPNをONにしてから続けてください。
echo.

REM --- Python の確認 ---
python --version >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [NG] Python が見つかりません >> "%LOG%"
  echo https://www.python.org からインストールし、 >> "%LOG%"
  echo インストール時に「Add Python to PATH」にチェックしてください。 >> "%LOG%"
  goto SHOW
)

REM --- 依存関係のインストール ---
if not exist .venv ( python -m venv .venv >> "%LOG%" 2>&1 )
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip >> "%LOG%" 2>&1
pip install -q -r requirements.txt >> "%LOG%" 2>&1

REM --- 接続テスト本体 ---
set PYTHONPATH=src
python scripts\check_nbs.py >> "%LOG%" 2>&1

:SHOW
echo.
type "%LOG%"
echo.
echo -------------------------------------------------
echo この結果は次のファイルにも保存されました:
echo   %LOG%
echo （このファイルを開いて内容を送ってもらえれば診断します）
echo -------------------------------------------------
echo.
pause
