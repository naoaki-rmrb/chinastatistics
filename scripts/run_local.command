#!/bin/bash
# Mac 用: このファイルをダブルクリックすると
# 依存インストール → データ取得 → Excel生成 まで自動で行います。
# 事前に「中国IPのVPN」をONにしておいてください。
cd "$(dirname "$0")/.." || exit 1
echo "==== 中国統計 Excel 生成（Mac） ===="
echo "※ 中国IPのVPNがONになっているか確認してください。"
echo

# Python3 の確認
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 が見つかりません。https://www.python.org からインストールしてください。"
  read -r -p "Enterで終了" _
  exit 1
fi

python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
echo "必要なライブラリを準備中..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "データを取得しています（初回は数分かかります）..."
export PYTHONPATH=src
python -m chinastats.cli build
status=$?

if [ $status -eq 0 ]; then
  echo
  echo "完了しました。Excel: output/china_indicators.xlsx"
  open output 2>/dev/null || true
else
  echo
  echo "取得に失敗しました。VPN(中国IP)がONか確認して、もう一度お試しください。"
fi
read -r -p "Enterで終了" _
