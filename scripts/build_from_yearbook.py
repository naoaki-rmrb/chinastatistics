"""中国統計年鑑(中文版)の .xls 群から、4テーマの省別・年次データを抽出し
Excel を生成する（NBS へ接続しない＝WAF回避のオフライン経路）。

対応表:
  gdp           <- 3-9 地区生产总值            (省別, 値＋指数 上年=100)
  retail        <- 15-12 社会消费品零售总额     (省別, 値＋比上年增长, 複数年)
  trade         <- 11-8 分地区货物进出口总额    (省別, 进出口/出口/进口)
  re_investment <- 19-15 分地区…房地产开发完成投资 (省別, 規模別合計=総投資)
  re_sold_area  <- 19-10 按用途分商品房销售面积  (全国・年次時系列)
  re_sold_value <- 19-11 按用途分商品房销售额    (全国・年次時系列)

使い方:
  python scripts/build_from_yearbook.py <年鑑zip または 中文版フォルダ> [出力xlsx]
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# 省の短縮名(年鑑表記) -> (code, 日本語)
REGIONS = [
    ("全国", "000000", "全国"), ("北京", "110000", "北京"), ("天津", "120000", "天津"),
    ("河北", "130000", "河北"), ("山西", "140000", "山西"), ("内蒙古", "150000", "内モンゴル"),
    ("辽宁", "210000", "遼寧"), ("吉林", "220000", "吉林"), ("黑龙江", "230000", "黒龍江"),
    ("上海", "310000", "上海"), ("江苏", "320000", "江蘇"), ("浙江", "330000", "浙江"),
    ("安徽", "340000", "安徽"), ("福建", "350000", "福建"), ("江西", "360000", "江西"),
    ("山东", "370000", "山東"), ("河南", "410000", "河南"), ("湖北", "420000", "湖北"),
    ("湖南", "430000", "湖南"), ("广东", "440000", "広東"), ("广西", "450000", "広西"),
    ("海南", "460000", "海南"), ("重庆", "500000", "重慶"), ("四川", "510000", "四川"),
    ("贵州", "520000", "貴州"), ("云南", "530000", "雲南"), ("西藏", "540000", "チベット"),
    ("陕西", "610000", "陝西"), ("甘肃", "620000", "甘粛"), ("青海", "630000", "青海"),
    ("宁夏", "640000", "寧夏"), ("新疆", "650000", "新疆"),
]
NAME2CODE = {r[0]: r[1] for r in REGIONS}
CODE2JA = {r[1]: r[2] for r in REGIONS}
ORDER = [r[1] for r in REGIONS]


def norm_region(s) -> str | None:
    """セル値を省コードに正規化。省名でなければ None。"""
    if not isinstance(s, str):
        return None
    key = re.sub(r"\s", "", s)
    key = key.replace("　", "")
    # 「北  京」→「北京」など
    if key in NAME2CODE:
        return NAME2CODE[key]
    # 一部表記ゆれ（黑龙江/黑龍江 等）は先頭2文字で近似
    for name, code in NAME2CODE.items():
        if key and (key.startswith(name) or name.startswith(key)):
            return code
    return None


def _num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def load_zip(path: Path) -> dict[str, bytes]:
    """zip/フォルダから {デコード済みパス: bytes} を返す（中文版のみ）。"""
    out: dict[str, bytes] = {}
    if path.is_dir():
        for p in path.rglob("*.xls"):
            out[str(p)] = p.read_bytes()
        return out
    z = zipfile.ZipFile(path)
    for n in z.namelist():
        if not n.lower().endswith(".xls"):
            continue
        try:
            d = n.encode("cp437").decode("utf-8")
        except Exception:
            try:
                d = n.encode("cp437").decode("gbk")
            except Exception:
                d = n
        if "中文版" in d or path.is_dir():
            out[d] = z.read(n)
    return out


def find(files: dict[str, bytes], fragment: str) -> bytes | None:
    for d, b in files.items():
        if fragment in d:
            return b
    return None


def read_xls(b: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(b), header=None, engine="xlrd")


# ---------------------------------------------------------------------
# 各表の抽出（tidy レコード: theme, region_code, year, series, value, yoy）
# ---------------------------------------------------------------------
def parse_retail(b: bytes) -> list[dict]:
    df = read_xls(b)
    # 年は row2 の 1,3 列に入る（例 2021, 2022）
    years = {}
    for c in range(1, df.shape[1]):
        y = _num(df.iat[2, c]) if df.shape[0] > 2 else None
        if y and 1990 <= y <= 2100:
            years[c] = int(y)
    recs = []
    for i in range(df.shape[0]):
        code = norm_region(df.iat[i, 0])
        if not code:
            continue
        for c, yr in years.items():
            val = _num(df.iat[i, c])
            yoy = _num(df.iat[i, c + 1]) if c + 1 < df.shape[1] else None
            if val is not None:
                recs.append(dict(theme="retail", region_code=code, year=yr,
                                 series="社会消费品零售总额", value=val, yoy=yoy))
    return recs


def parse_gdp(b: bytes) -> list[dict]:
    df = read_xls(b)
    year = 2022
    recs = []
    for i in range(df.shape[0]):
        code = norm_region(df.iat[i, 0])
        if not code:
            continue
        val = _num(df.iat[i, 1])  # 地区生产总值(亿元)
        # 指数(上年=100) の「地区生产总值」列。3-9 標準様式では col18。
        # 指数ブロック(地区GDP/一産/二産/三産/人均)の先頭 = 地区生产总值指数。
        idx = None
        if df.shape[1] > 18:
            v = _num(df.iat[i, 18])
            if v is not None and 80 <= v <= 130:
                idx = v
        if idx is None:
            # フォールバック: 指数ブロックらしき最初の 80〜130 を左から探す
            # (構成比の 80〜130 誤検出を避けるため col15 以降に限定)
            for c in range(15, df.shape[1]):
                v = _num(df.iat[i, c])
                if v is not None and 95 <= v <= 130:
                    idx = v
                    break
        yoy = round(idx - 100, 1) if idx is not None else None
        if val is not None:
            recs.append(dict(theme="gdp", region_code=code, year=year,
                             series="地区生产总值", value=val, yoy=yoy))
    return recs


def parse_trade(b: bytes) -> list[dict]:
    df = read_xls(b)
    year = 2022
    recs = []
    for i in range(df.shape[0]):
        code = norm_region(df.iat[i, 0])
        if not code:
            continue
        for c, name in [(1, "货物进出口"), (2, "货物出口"), (3, "货物进口")]:
            val = _num(df.iat[i, c])
            if val is not None:
                recs.append(dict(theme="trade", region_code=code, year=year,
                                 series=name, value=val, yoy=None))
    return recs


def parse_re_investment(b: bytes) -> list[dict]:
    df = read_xls(b)
    year = 2022
    recs = []
    for i in range(df.shape[0]):
        code = norm_region(df.iat[i, 0])
        if not code:
            continue
        # 規模別列(1..)の合計 = 房地产开发完成投资 総額
        vals = [_num(df.iat[i, c]) for c in range(1, df.shape[1])]
        vals = [v for v in vals if v is not None]
        if vals:
            recs.append(dict(theme="re_investment", region_code=code, year=year,
                             series="房地产开发完成投资", value=sum(vals), yoy=None))
    return recs


def parse_national_timeseries(b: bytes, theme: str, series: str) -> list[dict]:
    """19-10/19-11: col0=年, col1=総額（全国時系列）。"""
    df = read_xls(b)
    recs = []
    for i in range(df.shape[0]):
        y = _num(df.iat[i, 0])
        if y is None or not (1990 <= y <= 2100):
            continue
        val = _num(df.iat[i, 1])
        if val is not None:
            recs.append(dict(theme=theme, region_code="000000", year=int(y),
                             series=series, value=val, yoy=None))
    return recs


# ---------------------------------------------------------------------
# Excel 出力（省別は地区を行に、年を列に）
# ---------------------------------------------------------------------
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(bold=True, size=12)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def build(zip_path: str, out_path: str) -> None:
    files = load_zip(Path(zip_path))
    if not files:
        raise SystemExit(f"年鑑ファイルが見つかりません: {zip_path}")

    recs: list[dict] = []
    tbl = find(files, "15-12_社会消费品零售总额")
    if tbl is not None:
        recs += parse_retail(tbl)
    tbl = find(files, "3-9_地区生产总值")
    if tbl is not None:
        recs += parse_gdp(tbl)
    tbl = find(files, "11-8_分地区货物进出口总额")
    if tbl is not None:
        recs += parse_trade(tbl)
    tbl = find(files, "19-15_分地区按项目规模分房地产开发完成投资")
    if tbl is not None:
        recs += parse_re_investment(tbl)
    tbl = find(files, "19-10_按用途分商品房销售面积")
    if tbl is not None:
        recs += parse_national_timeseries(tbl, "re_sold_area", "商品房销售面积")
    tbl = find(files, "19-11_按用途分商品房销售额")
    if tbl is not None:
        recs += parse_national_timeseries(tbl, "re_sold_value", "商品房销售额")

    df = pd.DataFrame.from_records(recs)
    if df.empty:
        raise SystemExit("抽出できたデータがありません。")

    from openpyxl import Workbook
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "説明"
    info = [
        ("中国 省別・年次データ（統計年鑑2023より抽出）", TITLE_FONT),
        ("China provincial annual data extracted from Statistical Yearbook 2023", None),
        ("", None),
        ("出所: 中国統計年鑑2023（中文版）公式.xls", None),
        ("※ 年鑑は年次。省別は概ね2022年（小売は2021・2022）。", None),
        ("※ 前年比(YoY)は年鑑の公式値: 小売=比上年增长, GDP=指数(上年=100)より。", None),
        ("※ 月次データは別途 NBS(easyquery) から取得（VPN/プロキシ経由）。", None),
    ]
    for i, (t, f) in enumerate(info, 1):
        c = ws0.cell(i, 1, t)
        if f:
            c.font = f
    ws0.column_dimensions["A"].width = 80

    # テーマごとにシート（地区×年 の 値、YoY があれば併記）
    theme_titles = {
        "gdp": "GDP 地区生产总值", "retail": "小売 社会消费品零售总额",
        "trade": "貿易 货物进出口", "re_investment": "不動産 开发完成投资",
        "re_sold_area": "全国 商品房销售面积", "re_sold_value": "全国 商品房销售额",
    }
    for theme, title in theme_titles.items():
        sub = df[df["theme"] == theme]
        if sub.empty:
            continue
        ws = wb.create_sheet(title[:31])
        _write_theme(ws, title, sub)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"生成: {out_path}  （{len(df)} レコード, テーマ {df['theme'].nunique()}）")


def _write_theme(ws, title, sub) -> None:
    ws.cell(1, 1, title).font = TITLE_FONT
    series_list = list(dict.fromkeys(sub["series"].tolist()))
    years = sorted(sub["year"].unique().tolist())
    has_yoy = sub["yoy"].notna().any()

    # ヘッダ: 地区 | (系列×年 の 値) ... | (YoY×年) ...
    row = 3
    ws.cell(row, 1, "地区/地域").font = HDR_FONT
    ws.cell(row, 1).fill = HDR_FILL
    col = 2
    colmap = {}
    for s in series_list:
        for y in years:
            cell = ws.cell(row, col, f"{s}\n{y} 値")
            cell.font = HDR_FONT; cell.fill = HDR_FILL; cell.alignment = CENTER
            colmap[("val", s, y)] = col
            col += 1
    if has_yoy:
        for s in series_list:
            for y in years:
                if sub[(sub.series == s) & (sub.year == y)]["yoy"].notna().any():
                    cell = ws.cell(row, col, f"{s}\n{y} 前年比%")
                    cell.font = HDR_FONT; cell.fill = HDR_FILL; cell.alignment = CENTER
                    colmap[("yoy", s, y)] = col
                    col += 1

    # 地区は年鑑順
    present = set(sub["region_code"])
    r = row + 1
    for code in ORDER:
        if code not in present:
            continue
        ws.cell(r, 1, f"{CODE2JA.get(code, code)}")
        for (kind, s, y), c in colmap.items():
            rows = sub[(sub.region_code == code) & (sub.series == s) & (sub.year == y)]
            if rows.empty:
                continue
            v = rows.iloc[0]["yoy" if kind == "yoy" else "value"]
            if pd.notna(v):
                cell = ws.cell(r, c, float(v))
                cell.number_format = '0.0"%"' if kind == "yoy" else "#,##0.0"
        r += 1

    ws.freeze_panes = "B4"
    ws.column_dimensions["A"].width = 12
    for c in range(2, col):
        ws.column_dimensions[get_column_letter(c)].width = 14


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    zp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "output/china_yearbook_provincial.xlsx"
    build(zp, out)
