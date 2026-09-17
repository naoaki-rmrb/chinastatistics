"""レポート名・地区名の 中文/日本語/English 対訳辞書。

要約Excel(china_dg_all.xlsx)のシートタイトルと地区ラベルを
「中文 / 日本語 / English」で併記するために使う。
辞書に無いキーは中文のみをそのまま返す（安全側）。
"""
from __future__ import annotations

# ── 地区名: 中文 -> (日本語, English) ─────────────────────────
REGION_LABELS: dict[str, tuple[str, str]] = {
    "全国": ("全国", "National"),
    # 直轄市
    "北京市": ("北京市", "Beijing"),
    "天津市": ("天津市", "Tianjin"),
    "上海市": ("上海市", "Shanghai"),
    "重庆市": ("重慶市", "Chongqing"),
    # 省・自治区
    "河北省": ("河北省", "Hebei"),
    "山西省": ("山西省", "Shanxi"),
    "内蒙古自治区": ("内モンゴル自治区", "Inner Mongolia"),
    "辽宁省": ("遼寧省", "Liaoning"),
    "吉林省": ("吉林省", "Jilin"),
    "黑龙江省": ("黒竜江省", "Heilongjiang"),
    "江苏省": ("江蘇省", "Jiangsu"),
    "浙江省": ("浙江省", "Zhejiang"),
    "安徽省": ("安徽省", "Anhui"),
    "福建省": ("福建省", "Fujian"),
    "江西省": ("江西省", "Jiangxi"),
    "山东省": ("山東省", "Shandong"),
    "河南省": ("河南省", "Henan"),
    "湖北省": ("湖北省", "Hubei"),
    "湖南省": ("湖南省", "Hunan"),
    "广东省": ("広東省", "Guangdong"),
    "广西壮族自治区": ("広西チワン族自治区", "Guangxi"),
    "海南省": ("海南省", "Hainan"),
    "四川省": ("四川省", "Sichuan"),
    "贵州省": ("貴州省", "Guizhou"),
    "云南省": ("雲南省", "Yunnan"),
    "西藏自治区": ("チベット自治区", "Tibet"),
    "陕西省": ("陝西省", "Shaanxi"),
    "甘肃省": ("甘粛省", "Gansu"),
    "青海省": ("青海省", "Qinghai"),
    "宁夏回族自治区": ("寧夏回族自治区", "Ningxia"),
    "新疆维吾尔自治区": ("新疆ウイグル自治区", "Xinjiang"),
    # 36大中都市（省都・副省級市など）
    "石家庄市": ("石家荘市", "Shijiazhuang"),
    "太原市": ("太原市", "Taiyuan"),
    "呼和浩特市": ("フフホト市", "Hohhot"),
    "沈阳市": ("瀋陽市", "Shenyang"),
    "大连市": ("大連市", "Dalian"),
    "长春市": ("長春市", "Changchun"),
    "哈尔滨市": ("ハルビン市", "Harbin"),
    "南京市": ("南京市", "Nanjing"),
    "杭州市": ("杭州市", "Hangzhou"),
    "宁波市": ("寧波市", "Ningbo"),
    "合肥市": ("合肥市", "Hefei"),
    "福州市": ("福州市", "Fuzhou"),
    "厦门市": ("アモイ市", "Xiamen"),
    "南昌市": ("南昌市", "Nanchang"),
    "济南市": ("済南市", "Jinan"),
    "青岛市": ("青島市", "Qingdao"),
    "郑州市": ("鄭州市", "Zhengzhou"),
    "武汉市": ("武漢市", "Wuhan"),
    "长沙市": ("長沙市", "Changsha"),
    "广州市": ("広州市", "Guangzhou"),
    "深圳市": ("深圳市", "Shenzhen"),
    "南宁市": ("南寧市", "Nanning"),
    "海口市": ("海口市", "Haikou"),
    "成都市": ("成都市", "Chengdu"),
    "贵阳市": ("貴陽市", "Guiyang"),
    "昆明市": ("昆明市", "Kunming"),
    "拉萨市": ("ラサ市", "Lhasa"),
    "西安市": ("西安市", "Xi'an"),
    "兰州市": ("蘭州市", "Lanzhou"),
    "西宁市": ("西寧市", "Xining"),
    "银川市": ("銀川市", "Yinchuan"),
    "乌鲁木齐市": ("ウルムチ市", "Urumqi"),
    # 海外
    "日本": ("日本", "Japan"),
    "欧洲货币联盟": ("欧州通貨同盟(ユーロ圏)", "Euro Area"),
    "美国": ("米国", "United States"),
}

# ── レポート名: 中文 -> (日本語, English) ─────────────────────
REPORT_LABELS: dict[str, tuple[str, str]] = {
    "36大中城市居民消费价格分类指数(上年同月=100)(2016-)": (
        "36大中都市 消費者物価分類指数(前年同月=100)(2016-)",
        "CPI by Category, 36 Major Cities (same month prev yr=100)(2016-)",
    ),
    "全社会客货运输量": ("全社会 旅客・貨物輸送量", "Passenger & Freight Transport Volume (whole society)"),
    "分城乡居民消费和商品零售价格指数": (
        "都市・農村別 消費者物価・小売物価指数",
        "CPI & Retail Price Index by Urban/Rural",
    ),
    "分行业主要工业经济指标": ("業種別 主要工業経済指標", "Major Industrial Economic Indicators by Sector"),
    "各地区住宅开发规模与开、竣工面积增长情况": (
        "地域別 住宅開発規模・着工/竣工面積の伸び",
        "Residential Development Scale & Floor Space (Started/Completed) Growth by Region",
    ),
    "各地区住宅销售面积增长情况": ("地域別 住宅販売面積の伸び", "Residential Sales Floor Space Growth by Region"),
    "各地区办公楼开发规模与开、竣工面积增长情况": (
        "地域別 オフィスビル開発規模・着工/竣工面積の伸び",
        "Office Building Development & Floor Space Growth by Region",
    ),
    "各地区商业营业用房开发规模与开、竣工面积增长情况": (
        "地域別 商業用建物 開発規模・着工/竣工面積の伸び",
        "Commercial Building Development & Floor Space Growth by Region",
    ),
    "各地区商品房销售面积增长情况": (
        "地域別 商品住宅販売面積の伸び",
        "Commercial Building Sales Floor Space Growth by Region",
    ),
    "各地区固定资产住宅建设情况": ("地域別 固定資産 住宅建設状況", "Residential Construction (Fixed Assets) by Region"),
    "各地区固定资产投资构成情况": (
        "地域別 固定資産投資の構成",
        "Composition of Fixed Asset Investment by Region",
    ),
    "各地区固定资产投资（不含农户）": (
        "地域別 固定資産投資(農家除く)",
        "Fixed Asset Investment (excl. rural households) by Region",
    ),
    "各地区工业增加值增长速度": ("地域別 工業付加価値 伸び率", "Industrial Value-Added Growth Rate by Region"),
    "各地区工业生产者价格指数(上年同月=100)": (
        "地域別 工業生産者価格指数(前年同月=100)",
        "Producer Price Index by Region (same month prev yr=100)",
    ),
    "各地区房地产开发投资情况": ("地域別 不動産開発投資", "Real Estate Development Investment by Region"),
    "各地区房地产开发规模与开、竣工面积增长情况": (
        "地域別 不動産開発規模・着工/竣工面積の伸び",
        "Real Estate Development & Floor Space Growth by Region",
    ),
    "各地居民消费价格分类指数(上年同月=100)(2016-)": (
        "地域別 消費者物価分類指数(前年同月=100)(2016-)",
        "CPI by Category by Region (same month prev yr=100)(2016-)",
    ),
    "各地居民消费和商品零售价格指数": (
        "地域別 消費者物価・小売物価指数",
        "CPI & Retail Price Index by Region",
    ),
    "各月日本居民消费价格涨跌率、失业率和进出口贸易": (
        "月次 日本の消費者物価上昇率・失業率・輸出入",
        "Japan Monthly CPI Change, Unemployment & Trade",
    ),
    "各月欧元区居民消费价格涨跌率、失业率和进出口贸易": (
        "月次 ユーロ圏の消費者物価上昇率・失業率・輸出入",
        "Euro Area Monthly CPI Change, Unemployment & Trade",
    ),
    "各月美国居民消费价格涨跌率、失业率和进出口贸易": (
        "月次 米国の消費者物価上昇率・失業率・輸出入",
        "US Monthly CPI Change, Unemployment & Trade",
    ),
    "各行业固定资产投资(不含农户)": (
        "業種別 固定資産投資(農家除く)",
        "Fixed Asset Investment by Industry (excl. rural households)",
    ),
    "固定资产投资资金来源情况": ("固定資産投資 資金源泉", "Sources of Funds for Fixed Asset Investment"),
    "固定资产投资（不含农户）": ("固定資産投資(農家除く)", "Fixed Asset Investment (excl. rural households)"),
    "工业主要产品产量及增长速度": ("工業主要製品 生産量と伸び率", "Output & Growth of Major Industrial Products"),
    "工业分大类行业增加值增长速度": (
        "工業 大分類業種別 付加価値伸び率",
        "Industrial Value-Added Growth by Major Sector",
    ),
    "工业增加值增速": ("工業付加価値 伸び率", "Industrial Value-Added Growth Rate"),
    "工业生产者购进价格指数": ("工業生産者購入価格指数", "Industrial Producer Purchasing Price Index"),
    "房地产开发投资": ("不動産開発投資", "Real Estate Development Investment"),
    "按登记注册类型分的固定资产投资（不含农户）情况": (
        "登記種別 固定資産投資(農家除く)",
        "Fixed Asset Investment by Registration Type (excl. rural households)",
    ),
    "社会消费品零售总额": ("社会消費財小売総額", "Total Retail Sales of Consumer Goods"),
    "累计全国及36个大中城市居民消费价格分类指数(上年同期=100)(2016-)": (
        "累計 全国・36大中都市 消費者物価分類指数(前年同期=100)(2016-)",
        "Cumulative CPI by Category, National & 36 Major Cities (same period prev yr=100)(2016-)",
    ),
    "能源产品产量": ("エネルギー製品 生産量", "Output of Energy Products"),
    "邮电业务量完成情况": ("郵政・通信業務量", "Postal & Telecom Business Volume"),
    "限额以上企业（单位）商品零售类值": (
        "一定規模以上企業(単位) 商品小売額(品目別)",
        "Retail Sales by Category, Above-Designated-Size Enterprises",
    ),
}


def _compose(name: str) -> tuple[str, str]:
    """合成語（"_"連結）を部品辞書で日本語・英語に自動合成。未登録部品は中文のまま残す。"""
    from .token_labels import TOKEN_LABELS
    parts = [p.strip() for p in str(name).split("_") if p.strip()]
    ja_parts, en_parts = [], []
    for p in parts:
        pair = TOKEN_LABELS.get(p)
        if pair:
            ja_parts.append(pair[0]); en_parts.append(pair[1])
        else:
            ja_parts.append(p); en_parts.append(p)
    return "／".join(ja_parts), " / ".join(en_parts)


def indicator_trilingual(zh: str) -> str:
    """指標名(indicator)を「中文 / 日本語 / English」で返す（部品合成）。"""
    ja, en = _compose(zh)
    return f"{zh} / {ja} / {en}"


def indicator_ja_en(zh: str) -> tuple[str, str]:
    """指標名・内訳名の (日本語, English) を返す。対訳グロッサリ用。"""
    return _compose(zh)


def region_trilingual(zh: str) -> str:
    """地区名を「中文 / 日本語 / English」で返す。未登録は中文のみ。"""
    pair = REGION_LABELS.get(zh)
    if not pair:
        return zh
    ja, en = pair
    return f"{zh} / {ja} / {en}"


def report_trilingual(zh: str) -> str:
    """レポート名を「中文 / 日本語 / English」で返す。未登録は中文のみ。"""
    pair = REPORT_LABELS.get(zh)
    if not pair:
        return zh
    ja, en = pair
    return f"{zh} / {ja} / {en}"
