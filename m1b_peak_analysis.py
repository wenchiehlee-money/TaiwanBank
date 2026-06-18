# -*- coding: utf-8 -*-
"""
表19-7 頭部第一波最大日成交量佔貨幣供給額(M1B)比重分析表
對應圖片 (115年5月15日)，單位：億元

結構說明：
  每個波段高點循環有兩列：
    列1 = 上市（TWSE 集中市場）最大日成交量
    列2 = 上櫃（TPEX 店頭市場）最大日成交量
  再加一列市場小計。

M1B 單位換算：
  CBC EF15M01.csv 原始值單位為百萬元，÷100 = 億元
  例: 23,288,445 百萬元 ÷ 100 = 232,884 億元（符合圖片）
"""

import io
import sys
import time
import warnings
import requests
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

CBC_M1B_URL = (
    "https://www.cbc.gov.tw/public/data/OpenData/"
    "%E7%B6%93%E7%A0%94%E8%99%95/EF15M01.csv"
)
TWSE_API = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
TPEX_API = (
    "https://www.tpex.org.tw/web/stock/aftertrading/"
    "daily_trading_index/st41_result.php"
)

# ─────────────────────────────────────────────────────────────────────────────
# 波段高點定義
#
# market   : 上市 | 上櫃
# type     : 大漲 | 中漲 | ""
# peak_date: 波段高點日期（民國 XX.MM.DD）
# peak_pts : 波段高點指數
# max_vol  : 最大日成交量（億元）None=動態抓取
# vol_date : 最大日成交量發生日期（民國 XX.MM.DD）
# m1b_ym   : 使用哪個月份 of M1B（YYYYMM）
# group    : 同一市場循環的群組識別
# group_lbl: 小計列顯示的標籤
# ─────────────────────────────────────────────────────────────────────────────
PEAKS = [
    # ── 1989 (78年) 大漲 上市 ─────────────────────────────────────────────
    dict(market="上市", jl_type="金龍大漲", type="大漲",
         peak_date="1989.09.26", peak_pts=10843.96,
         max_vol=1941.71, vol_date="1989.08.28", m1b_ym="198908",
         group="G78", group_lbl=None),         # 無小計，獨立列
    # ── 1990 (79年) 大漲 上市 ─────────────────────────────────────────────
    dict(market="上市", jl_type="金龍大漲", type="大漲",
         peak_date="1990.02.12", peak_pts=12682.41,
         max_vol=2162.02, vol_date="1990.03.16", m1b_ym="199003",
         group="G79", group_lbl=None),
    # ── 1997 (86年) 大漲 上市+上櫃 ──────────────────────────────────────
    dict(market="上市", jl_type="金龍大漲", type="大漲",
         peak_date="1997.08.27", peak_pts=10256.10,
         max_vol=2968.88, vol_date="1997.07.17", m1b_ym="199707",
         group="G86", group_lbl="1997/08"),
    dict(market="上櫃", jl_type="金龍大漲", type="大漲",
         peak_date="1997.08.06", peak_pts=348.50,
         max_vol=299.20,  vol_date="1997.08.05", m1b_ym="199708",
         group="G86", group_lbl=None),
    # ── 1998 (87年) 中漲 上市+上櫃 ──────────────────────────────────────
    dict(market="上市", jl_type="金龍慢漲", type="中跌",
         peak_date="1998.02.27", peak_pts=9378.52,
         max_vol=2776.92, vol_date="1998.02.06", m1b_ym="199802",
         group="G87", group_lbl="1998/02"),
    dict(market="上櫃", jl_type="金龍慢漲", type="中跌",
         peak_date="1998.02.24", peak_pts=286.57,
         max_vol=196.25,  vol_date="1998.02.23", m1b_ym="199802",
         group="G87", group_lbl=None),
    # ── 1999 (88年) 中漲 上市+上櫃 ──────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中漲",
         peak_date="1999.07.03", peak_pts=8710.71,
         max_vol=2298.81, vol_date="1999.06.23", m1b_ym="199906",
         group="G88", group_lbl="1999/05-07"),
    dict(market="上櫃", jl_type="金龍中漲", type="中漲",
         peak_date="1999.05.11", peak_pts=184.08,
         max_vol=120.47,  vol_date="1999.04.10", m1b_ym="199904",
         group="G88", group_lbl=None),
    # ── 2000 (89年) 中漲 上市+上櫃 ──────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2000.02.18", peak_pts=10393.59,
         max_vol=3256.01, vol_date="2000.01.11", m1b_ym="200001",
         group="G89", group_lbl="2000/02-04"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2000.04.11", peak_pts=329.47,
         max_vol=571.45,  vol_date="2000.04.11", m1b_ym="200004",
         group="G89", group_lbl=None),
    # ── 2007 (96年) 大漲 上市+上櫃 ──────────────────────────────────────
    dict(market="上市", jl_type="金龍大漲", type="大跌",
         peak_date="2007.10.30", peak_pts=9859.62,
         max_vol=3219.16, vol_date="2007.07.26", m1b_ym="200707",
         group="G96", group_lbl="2007/07-10"),
    dict(market="上櫃", jl_type="金龍大漲", type="大跌",
         peak_date="2007.07.26", peak_pts=238.35,
         max_vol=1067.55, vol_date="2007.07.26", m1b_ym="200707",
         group="G96", group_lbl=None),
    # ── 2011 (100年) 中漲 上市+上櫃 ─────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2011.01.28", peak_pts=9220.69,
         max_vol=None,    vol_date="2011.01.06", m1b_ym="201101",
         group="G100", group_lbl="2011/01-03"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2011.03.04", peak_pts=149.33,
         max_vol=None,    vol_date="2011.01.26", m1b_ym="201101",
         group="G100", group_lbl=None),
    # ── 2015 (104年) 中漲 上市+上櫃 ─────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2015.04.28", peak_pts=10014.28,
         max_vol=None,    vol_date="2015.04.24", m1b_ym="201504",
         group="G104", group_lbl="2015/03-04"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2015.03.24", peak_pts=148.66,
         max_vol=None,    vol_date="2015.03.24", m1b_ym="201503",
         group="G104", group_lbl=None),
    # ── 2018 (107年) 中漲 上市+上櫃 ─────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2018.01.23", peak_pts=11270.18,
         max_vol=None,    vol_date="2018.01.23", m1b_ym="201801",
         group="G107", group_lbl="2018/01"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2018.01.25", peak_pts=154.58,
         max_vol=None,    vol_date="2018.01.23", m1b_ym="201801",
         group="G107", group_lbl=None),
    # ── 2021 (110年) 中漲 上市+上櫃 ─────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2021.07.15", peak_pts=18034.19,
         max_vol=None,    vol_date="2021.05.12", m1b_ym="202105",
         group="G110", group_lbl="2021/07"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2021.07.27", peak_pts=225.05,
         max_vol=None,    vol_date="2021.07.13", m1b_ym="202107",
         group="G110", group_lbl=None),
    # ── 2022 (111年) 中漲 上市+上櫃 ─────────────────────────────────────
    # M1B 使用 202112 (110年12月，月底前最新公布值)
    dict(market="上市", jl_type="金龍中漲", type="中漲",
         peak_date="2022.01.05", peak_pts=18619.61,
         max_vol=None,    vol_date="2022.01.05", m1b_ym="202112",
         group="G111", group_lbl="2022/01"),
    dict(market="上櫃", jl_type="金龍中漲", type="中漲",
         peak_date="2022.01.03", peak_pts=238.92,
         max_vol=None,    vol_date="2022.01.07", m1b_ym="202112",
         group="G111", group_lbl=None),
    # ── 2024 (113年) 中漲 上市+上櫃 ─────────────────────────────────────
    dict(market="上市", jl_type="金龍中漲", type="中跌",
         peak_date="2024.07.11", peak_pts=24416.67,
         max_vol=None,    vol_date="2024.04.19", m1b_ym="202404",
         group="G113", group_lbl="2024/07"),
    dict(market="上櫃", jl_type="金龍中漲", type="中跌",
         peak_date="2024.07.17", peak_pts=283.32,
         max_vol=None,    vol_date="2024.03.07", m1b_ym="202403",
         group="G113", group_lbl=None),
    # ── 2026 (115年) 中漲 上市+上櫃 ─────────────────────────────────────
    # M1B 使用 202603 (115年3月，製表時最新公布值)
    dict(market="上市", jl_type="金龍中漲", type="中漲",
         peak_date="2026.04.15", peak_pts=42408.66,
         max_vol=None,    vol_date="2026.05.06", m1b_ym="202603",
         group="G115", group_lbl="2026/04-05"),
    dict(market="上櫃", jl_type="金龍中漲", type="中漲",
         peak_date="2026.05.14", peak_pts=431.74,
         max_vol=None,    vol_date="2026.05.06", m1b_ym="202603",
         group="G115", group_lbl=None),
]


# ── 輔助函式 ──────────────────────────────────────────────────────────────────

def load_m1b() -> dict[str, float]:
    """下載 CBC M1B 月平均，回傳 {YYYYMM: M1B日平均(億元)}。百萬元 ÷ 100 = 億元。"""
    print("下載 CBC M1B 資料…", flush=True)
    resp = requests.get(CBC_M1B_URL, timeout=30, verify=False)
    resp.encoding = "utf-8-sig"
    df = pd.read_csv(io.StringIO(resp.text))
    col = [c for c in df.columns if "Ｍ１Ｂ" in c and "年增率" not in c][0]
    out = {}
    for _, row in df.iterrows():
        p = str(row[df.columns[0]])
        if "M" not in p:
            continue
        yyyymm = p.replace("M", "")
        try:
            out[yyyymm] = round(float(row[col]) / 100, 0)   # 百萬元 → 億元
        except (ValueError, TypeError):
            pass
    return out


def _ad_to_roc(ad_date: str) -> str:
    """'2021.05.12' → '110.05.12'"""
    p = ad_date.replace("/", ".").split(".")
    roc_year = int(p[0]) - 1911
    return f"{roc_year}.{p[1]}.{p[2]}"


def _roc_to_yyyymm(roc_date: str) -> str:
    """'110.05.12' → '202105'"""
    p = roc_date.replace("/", ".").split(".")
    return f"{int(p[0])+1911}{p[1]}"


def _roc_to_twse_ym(roc_date: str) -> str:
    """'110.05.12' → '11005' (TWSE API 格式)"""
    yyyymm = _roc_to_yyyymm(roc_date)
    return yyyymm  # 後面直接 + "01"


def _roc_to_display(roc_date: str) -> str:
    """'110.05.12' → '110/05/12'"""
    return roc_date.replace(".", "/")


def fetch_twse_day(vol_date_ad: str, retries: int = 5) -> float | None:
    """取得 TWSE 指定日的成交金額（億元）。"""
    vol_date_roc = _ad_to_roc(vol_date_ad)
    yyyymm  = _roc_to_yyyymm(vol_date_roc)
    target  = _roc_to_display(vol_date_roc)
    for attempt in range(retries):
        try:
            r = requests.get(TWSE_API,
                             params={"response": "json", "date": yyyymm + "01"},
                             timeout=20)
            d = r.json()
            if d.get("stat") != "OK" or not d.get("data"):
                time.sleep(2); continue
            rows = d["data"]
            # 驗證月份正確
            first_ym = _first_ym_twse(rows[0][0])
            if first_ym != yyyymm:
                time.sleep(3); continue
            for row in rows:
                if row[0] == target:
                    return round(float(row[2].replace(",", "")) / 1e8, 2)
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def _first_ym_twse(roc_date: str) -> str:
    p = roc_date.replace("/", ".").split(".")
    return f"{int(p[0])+1911}{p[1]}"


def fetch_tpex_day(vol_date_ad: str, retries: int = 5) -> float | None:
    """取得 TPEX 指定日的上櫃成交金額（億元）。"""
    vol_date_roc = _ad_to_roc(vol_date_ad)
    p    = vol_date_roc.split(".")
    roc_ym_enc = f"{p[0]}%2F{p[1]}"     # e.g. 110%2F07
    target = _roc_to_display(vol_date_roc)  # e.g. 110/07/13
    for attempt in range(retries):
        try:
            r = requests.get(
                TPEX_API,
                params={"d": f"{p[0]}/{p[1]}", "o": "json"},
                timeout=20, verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            d = r.json()
            tables = d.get("tables", [])
            if not tables:
                time.sleep(2); continue
            data = tables[0].get("data", [])
            for row in data:
                if row[0] == target:
                    # 金額單位：千元 → 億元 (÷ 1e5)
                    return round(float(row[2].replace(",", "")) / 1e5, 2)
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


# ── 主流程 ───────────────────────────────────────────────────────────────────

def build_table(m1b: dict[str, float]) -> list[dict]:
    rows = []
    groups: dict[str, dict] = {}

    for i, pk in enumerate(PEAKS):
        m1b_val = m1b.get(pk["m1b_ym"])
        g = pk["group"]

        # 取成交量
        vol = pk["max_vol"]
        if vol is None:
            print(f"  抓 {pk['market']} {pk['vol_date']} 成交量…", flush=True)
            if pk["market"] == "上市":
                vol = fetch_twse_day(pk["vol_date"])
            else:
                vol = fetch_tpex_day(pk["vol_date"])
            time.sleep(1.0)

        ratio = round(vol / m1b_val * 100, 2) if vol and m1b_val else None

        # 群組小計累計
        if g not in groups:
            groups[g] = {"vols": [], "m1b_first": m1b_val, "lbl": None}
        if pk.get("group_lbl"):
            groups[g]["lbl"] = pk["group_lbl"]
        if vol:
            groups[g]["vols"].append(vol)

        rows.append({
            "market":         pk["market"],
            "jl_type":        pk.get("jl_type", ""),
            "type":           pk["type"],
            "peak_date":      pk["peak_date"],
            "peak_pts":       pk["peak_pts"],
            "max_vol":        vol,
            "vol_date":       pk["vol_date"],
            "m1b":            m1b_val,
            "ratio":          ratio,
            "group":          g,
            "is_subtotal":    False,
        })

        # 是否插入小計（群組最後一筆 or 無小計的獨立列不插入）
        next_pk = PEAKS[i + 1] if i + 1 < len(PEAKS) else None
        is_group_end = (next_pk is None) or (next_pk["group"] != g)
        gdata = groups[g]
        if is_group_end and gdata.get("lbl"):
            total_vol = round(sum(gdata["vols"]), 2)
            sub_ratio = (
                round(total_vol / gdata["m1b_first"] * 100, 2)
                if gdata["m1b_first"] else None
            )
            rows.append({
                "market":      "市場小計",
                "jl_type":     "",
                "type":        "",
                "peak_date":   gdata["lbl"],
                "peak_pts":    None,
                "max_vol":     total_vol,
                "vol_date":    "",
                "m1b":         None,
                "ratio":       sub_ratio,
                "group":       g,
                "is_subtotal": True,
            })

    return rows


def print_table(rows: list[dict]):
    W = 120
    print()
    print("=" * W)
    print("  表19-7  頭部第一波最大日成交量佔貨幣供給額(M1B)比重分析表"
          "            單位：億元")
    print("  資料來源：CBC EF15M01.csv (M1B百萬元÷100=億元)；TWSE FMTQIK；TPEX st41")
    print("=" * W)
    header = (f"{'市場':<4} {'金龍類型':<8} {'實質類型':<8}  {'波段高點日期':^12}  {'波段高點(點)':>12}  "
          f"{'最大日成交量':>14}  {'最大日成交量日期':^12}  {'M1B日平均':>12}  {'比重%':>8}")
    print(header)
    SEP = "-" * W
    print(SEP)

    prev_group = None
    for r in rows:
        if r["group"] != prev_group and prev_group is not None and not r["is_subtotal"]:
            print()
        prev_group = r["group"]

        if r["is_subtotal"]:
            vol_s = f"{r['max_vol']:>14,.2f}" if r["max_vol"] else f"{'':>14}"
            rat_s = f"{r['ratio']:>7.2f}%" if r["ratio"] else ""
            print(SEP)
            print(f"{'【市場小計】':<4} {'':8} {'':8}  {r['peak_date']:^12}  {'':>12}  "
                  f"{vol_s}  {'':^12}  {'':>12}  {rat_s}")
            print(SEP)
        else:
            pts_s = f"{r['peak_pts']:>12,.2f}" if r["peak_pts"] else f"{'':>12}"
            vol_s = f"{r['max_vol']:>14,.2f}" if r["max_vol"] else f"{'N/A':>14}"
            m1b_s = f"{r['m1b']:>12,.0f}" if r["m1b"] else f"{'':>12}"
            rat_s = f"{r['ratio']:>7.2f}%" if r["ratio"] else ""
            print(f"{r['market']:<4} {r['jl_type']:<8} {r['type']:<8}  {r['peak_date']:^12}  "
                  f"{pts_s}  {vol_s}  {r['vol_date']:^12}  {m1b_s}  {rat_s}")

    print("=" * W)
    print()
    print("  備註：")
    print("  * 上市成交量來自 TWSE FMTQIK API（集中市場成交金額）")
    print("  * 上櫃成交量來自 TPEX st41 API（店頭市場成交金額，仟元÷1e5=億元）")
    print("  * M1B：CBC EF15M01 月平均值（百萬元）÷ 100 = 億元")
    print("  * 以2026年3月M1B 300,861億的6.27%推估，上市最大日成交量約18,802億元")
    print("  * 以2026年3月M1B 300,861億的8.40%(2000年度水準)推估，最大日成交量約25,272億元")


def main():
    m1b = load_m1b()

    # 驗證幾個關鍵月份
    checks = [("202105", 232884), ("202107", 237605), ("202112", 247580), ("202603", 300861)]
    print("\nM1B 驗證（應符合圖片值）：")
    for ym, expected in checks:
        got = m1b.get(ym, "N/A")
        ok  = "✓" if isinstance(got, float) and abs(got - expected) < 10 else "≠"
        print(f"  {ym}: {got:,.0f} 億  {ok}  (圖片={expected:,})")
    print()

    rows = build_table(m1b)
    print_table(rows)

    # 存 CSV
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "group"} for r in rows])
    df.to_csv("m1b_peak_result.csv", index=False, encoding="utf-8-sig")
    print("結果已儲存至 m1b_peak_result.csv")


if __name__ == "__main__":
    main()
