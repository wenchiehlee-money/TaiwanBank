# -*- coding: utf-8 -*-
"""
從最大日成交量估貨幣供給額(M1B)比重分析表
資料來源:
  - M1B: 中央銀行開放資料 (data.gov.tw/dataset/6024)
  - 大盤每日成交金額: 台灣證券交易所 TWSE OpenAPI
"""

import io
import time
import warnings
import requests
import pandas as pd

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

M1B_CSV_URL = "https://www.cbc.gov.tw/public/data/OpenData/%E7%B6%93%E7%A0%94%E8%99%95/EF15M01.csv"
TWSE_API    = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"


def fetch_m1b() -> pd.DataFrame:
    """下載並解析央行 M1B 月平均資料。回傳 period(YYYYMM), m1b(億元) 兩欄。"""
    resp = requests.get(M1B_CSV_URL, timeout=30, verify=False)
    resp.encoding = "utf-8-sig"
    df = pd.read_csv(io.StringIO(resp.text))

    # 找出 M1B 原始值欄位 (包含全形「Ｍ１Ｂ」且不含「年增率」)
    m1b_col = [c for c in df.columns if "Ｍ１Ｂ" in c and "年增率" not in c][0]
    period_col = df.columns[0]

    result = df[[period_col, m1b_col]].copy()
    result.columns = ["period_raw", "m1b_億元"]
    result = result.dropna()

    # 期間格式如 2024M01 → 202401
    result["period"] = result["period_raw"].str.replace("M", "", regex=False)
    result["m1b_億元"] = pd.to_numeric(result["m1b_億元"], errors="coerce")
    return result[["period", "m1b_億元"]].dropna()


def _roc_to_ad(roc_date: str) -> str:
    """民國年月轉西元年月，如 '105/01/04' → '201601'"""
    parts = roc_date.split("/")
    year = int(parts[0]) + 1911
    return f"{year}{parts[1]}"


def fetch_twse_monthly(yyyymm: str, retries: int = 5) -> float | None:
    """
    取得指定年月(如 '202401')的大盤最大單日成交金額(億元)。
    TWSE API 回傳整月每日資料，取 max(成交金額)。
    會驗證回應日期與請求月份一致，避免 API 限速時返回快取舊資料。
    """
    date_str = yyyymm + "01"
    for attempt in range(retries):
        try:
            resp = requests.get(
                TWSE_API,
                params={"response": "json", "date": date_str},
                timeout=20,
            )
            data = resp.json()
            if data.get("stat") != "OK" or not data.get("data"):
                time.sleep(2)
                continue
            rows = data["data"]
            # 驗證：回應的第一筆日期年月需與請求一致
            first_date_ym = _roc_to_ad(rows[0][0])  # e.g. '201601'
            if first_date_ym != yyyymm:
                time.sleep(3)
                continue
            # fields: 日期, 成交股數, 成交金額, 成交筆數, 加權股價指數, 漲跌點數
            amounts = [float(row[2].replace(",", "")) for row in rows]
            return max(amounts) / 1e8  # 元 → 億元
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def build_table(start_year: int = 2010, end_year: int = 2026) -> pd.DataFrame:
    print("下載 M1B 資料中…")
    m1b_df = fetch_m1b()

    # 篩選年份範圍
    m1b_df = m1b_df[
        (m1b_df["period"].str[:4].astype(int) >= start_year) &
        (m1b_df["period"].str[:4].astype(int) <= end_year)
    ].reset_index(drop=True)

    print(f"共 {len(m1b_df)} 個月份，開始下載 TWSE 成交量…")
    max_vol_list = []
    for i, row in m1b_df.iterrows():
        yyyymm = row["period"]
        vol = fetch_twse_monthly(yyyymm)
        max_vol_list.append(vol)
        if (i + 1) % 12 == 0:
            print(f"  已完成 {i+1}/{len(m1b_df)} 個月")
        time.sleep(1.0)  # TWSE 限速：每5秒最多3次請求

    m1b_df["最大日成交金額_億元"] = max_vol_list
    m1b_df = m1b_df.dropna(subset=["最大日成交金額_億元"])

    # m1b_億元 實際單位為百萬元（CBC CSV原始值），需 ÷100 轉億元後再算比重
    m1b_df["M1B佔比_%"] = (
        m1b_df["最大日成交金額_億元"] / (m1b_df["m1b_億元"] / 100) * 100
    ).round(4)

    m1b_df["年月"] = (
        m1b_df["period"].str[:4] + "/" + m1b_df["period"].str[4:]
    )

    m1b_df["M1B月平均(億元)"] = (m1b_df["m1b_億元"] / 100).round(0)
    return m1b_df[["年月", "M1B月平均(億元)", "最大日成交金額_億元", "M1B佔比_%"]]


def main():
    df = build_table(start_year=2015, end_year=2026)
    df["M1B月平均(億元)"]  = df["M1B月平均(億元)"].map(lambda x: f"{x:,.0f}")   # 億元
    df["最大日成交金額_億元"] = df["最大日成交金額_億元"].map(lambda x: f"{x:,.1f}")
    df["M1B佔比_%"]         = df["M1B佔比_%"].map(lambda x: f"{x:.4f}%")

    print("\n===== 從最大日成交量估貨幣供給額(M1B)比重分析表 =====")
    print(df.to_string(index=False))

    out_path = "m1b_analysis_result.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n結果已儲存至 {out_path}")


if __name__ == "__main__":
    main()
