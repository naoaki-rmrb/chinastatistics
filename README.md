# chinastatistics — 中国 全国・省別 経済指標の自動収集

中国の**全国**および**31省・自治区・直轄市**（北京・上海・天津・重慶の4直轄市を含む）の
経済指標を国家統計局(NBS)から毎月自動取得し、**前年比・前月比付きの Excel** を
生成・更新するツールです。GitHub Actions で毎月自動実行され、成果物を
`output/china_indicators.xlsx` にコミットします。

## 対象指標

| key | 中文 | 日本語 | English | 頻度 |
|---|---|---|---|---|
| gdp | 地区生产总值/国内生产总值 | 域内総生産/国内総生産 | Gross Regional/Domestic Product | 四半期 |
| retail | 社会消费品零售总额 | 社会消費財小売総額 | Total Retail Sales of Consumer Goods | 月次 |
| re_investment | 房地产开发投资完成额 | 不動産開発投資完成額 | Real Estate Development Investment | 月次(累計) |
| re_sold_area | 商品房销售面积 | 商品住宅販売面積 | Floor Space of Buildings Sold | 月次(累計) |
| re_sold_value | 商品房销售额 | 商品住宅販売額 | Sales of Buildings (value) | 月次(累計) |
| exports | 出口总额 | 輸出総額 | Total Exports | 月次 |
| imports | 进口总额 | 輸入総額 | Total Imports | 月次 |

指標名は `config/indicators.yaml` に**中国語・日本語・英語・単位**を定義。

## 前年比を2系統で持つ理由（改定検知）

各指標について次の列を出します：

- **値** … NBS から取得した水準
- **公式前年比** … NBS が発表する同比（増速）を**そのまま取得**
- **計算前年比** … Excel の**数式**で `今年値 ÷ 去年同月値 − 1`
- **乖離** … `計算 − 公式`（％ポイント）
- **前月比 / 前期比** … Excel の数式で計算
- 累計指標は **単月（累計差分で復元）** と**単月前月比**も

中国は前年の水準をこっそり下方改定して当年の前年比を高く見せることがあるため、
「NBS公表の前年比」と「表の上で自分で計算した前年比」を**並べて乖離を見える化**します。
さらに毎月コミットする性質を使い、**改定検知シート**で
「前回スナップショット時点の過去値」との差分（下方改定の有無・幅）を表示します。

## Excel の構成（`output/china_indicators.xlsx`）

- `説明` … データ源・注意・最終更新・解決済み指標コード
- `指標一覧` … 3言語の指標名・単位一覧
- `改定検知` … 前回からの過去値改定
- `<指標key>` … 地区(列)×時点(行) の行列を、値/公式前年比/計算前年比/乖離/前月比…と縦に積む

## 使い方

### 自動（推奨）
`.github/workflows/update.yml` が毎月20日(UTC) に実行。手動起動も可能
（Actions 画面の「Run workflow」）。生成物は自動コミットされます。

### 手動実行
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m chinastats.cli build            # 全指標を取得
PYTHONPATH=src python -m chinastats.cli build --only retail,gdp
```

### 指標コードの確認（トラブル時）
NBS の指標コードは名前から自動解決していますが、ずれた場合は
ツリーをダンプして候補名を `config/indicators.yaml` に追記します。
```bash
PYTHONPATH=src python -m chinastats.cli discover --db fsyd --out fsyd_tree.json
```

### オフライン検証（合成データ）
NBS へ接続せず Excel 生成のパイプラインを確認します。
```bash
PYTHONPATH=src python -m chinastats.cli demo
PYTHONPATH=src python -m pytest tests/ -q
```

## データ源と注意点

- 出所: 国家統計局 (NBS) データポータル `https://data.stats.gov.cn`
- **GDP は四半期のみ**（月次GDPは存在しない）
- 月次系列は**概ね1990年代以降**。1945〜1980年代の月次数値は存在しない
- **1月は春節の影響で単月非公表**（1-2月累計）のことが多い
- 投資・販売系は**累計値**で公表。単月は累計差分で復元
- 貿易は当面 NBS 内の系列を使用（将来、税関総署ベースに拡張可能な設計）

## 構成

```
config/
  indicators.yaml   指標定義(中/日/英・単位・照合名・DB)
  regions.yaml      全国+31省の地区コード
  settings.yaml     取得期間・タイムアウト等
src/chinastats/
  nbs_client.py     NBS easyquery クライアント
  resolver.py       指標名→コード解決（ツリー探索）
  fetch.py          指標×地区の時系列取得
  transform.py      前年比/前月比/単月/改定検知
  excel_writer.py   3言語ヘッダ付き Excel 生成
  cli.py            build / discover / demo
.github/workflows/update.yml  月次自動実行
output/china_indicators.xlsx  成果物（自動コミット）
```
