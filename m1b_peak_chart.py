# -*- coding: utf-8 -*-
import os
import csv
import io
import requests
import pandas as pd
import yfinance as yf
import urllib3

# 停用 SSL 警告 (因為央行網站可能會有證書檢驗警告)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def generate_svg(csv_path: str, start_date: str = "1997-07-02") -> str:
    # 1. 讀取 CSV 數據並分組，提取歷史波段高點
    data = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        group_rows = []
        
        for row in reader:
            is_sub = (row.get("is_subtotal") == "True")
            market = row.get("market")
            
            if is_sub:
                group_rows.append(row)
                data.append(process_group(group_rows))
                group_rows = []
            elif market == "上市":
                if group_rows:
                    data.append(process_group(group_rows))
                group_rows = [row]
            else:
                group_rows.append(row)
                
        if group_rows:
            data.append(process_group(group_rows))
            
    # 2. 用 yfinance 下載 TAIEX 每日數據
    print(f"下載 TAIEX 歷史每日成交與收盤數據 (自 {start_date} 起)...")
    df = yf.download("^TWII", start=start_date, end="2026-06-18")
    
    # 拍平 MultiIndex 欄位 (yfinance 有時會傳回多級 index)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.dropna(subset=["Close", "Volume"])
    
    # 3. 下載並加載 CBC M1B 月平均數據
    print("下載央行 M1B 月平均歷史數據...")
    CBC_M1B_URL = "https://www.cbc.gov.tw/public/data/OpenData/%E7%B6%93%E7%A0%94%E8%99%95/EF15M01.csv"
    m1b_dict = {}
    try:
        resp = requests.get(CBC_M1B_URL, timeout=30, verify=False)
        resp.encoding = "utf-8-sig"
        m1b_df_raw = pd.read_csv(io.StringIO(resp.text))
        col = [c for c in m1b_df_raw.columns if "Ｍ１Ｂ" in c and "年增率" not in c][0]
        
        for _, row in m1b_df_raw.iterrows():
            p = str(row[m1b_df_raw.columns[0]])
            if "M" not in p:
                continue
            yyyymm = p.replace("M", "")
            try:
                m1b_dict[yyyymm] = float(row[col]) / 100 # 百萬元 -> 億元
            except:
                pass
    except Exception as e:
        print(f"下載 M1B 失敗: {e}")
        
    # 將 M1B 數據對齊到每日交易日
    m1b_series = []
    last_m1b = 0.0
    for dt in df.index:
        ym = dt.strftime("%Y%m")
        val = m1b_dict.get(ym, last_m1b)
        if val > 0:
            last_m1b = val
        m1b_series.append(val)
    df["M1B"] = m1b_series
    
    # 4. 圖表基礎尺寸設計
    W, H = 1000, 600
    margin_left, margin_right = 80, 80
    margin_top, margin_bottom = 120, 70
    
    chart_w = W - margin_left - margin_right
    chart_h = H - margin_top - margin_bottom
    
    # 決定顏色
    colors = {
        "大漲": "#e53935",  # 亮紅
        "大跌": "#b71c1c",  # 深紅
        "中漲": "#2e7d32",  # 綠
        "中跌": "#ef6c00",  # 橘
    }
    
    svg_parts = []
    # 頂部宣告與卡片背景
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%">')
    svg_parts.append(f'  <rect width="{W}" height="{H}" rx="16" fill="#ffffff" stroke="#eceff1" stroke-width="1.5"/>')
    
    # 標題
    start_year_str = start_date.split("-")[0]
    svg_parts.append(f'  <text x="{W/2}" y="35" font-family="system-ui, -apple-system, sans-serif" font-size="20" font-weight="bold" fill="#1e293b" text-anchor="middle">台股指數、M1B 資金活水與成交量歷史走勢對照圖 ({start_year_str}年~至今)</text>')
    
    # 標註說明（Subtitle / Annotations of both logics）
    svg_parts.append(f'  <text x="{margin_left}" y="65" font-family="system-ui, -apple-system, sans-serif" font-size="11.5" font-weight="bold" fill="#475569">【杜金龍大師命名邏輯】：依歷史波段漲幅分類（金龍大漲/中漲/慢漲）</text>')
    svg_parts.append(f'  <text x="{margin_left}" y="85" font-family="system-ui, -apple-system, sans-serif" font-size="11.5" font-weight="bold" fill="#475569">【實質風險警示邏輯】：依高點後修正跌幅分類（大跌：崩盤 &gt; 35% | 中跌：修正 15-35% | 大漲/中漲：多頭續強）</text>')

    # 5. 雙 Y 軸刻度線與網格線 (0% 到 100%)
    max_y_left = 50000.0   # 左軸：股價點數 50,000 點
    max_y_right = 350000.0  # 右軸：M1B 餘額 35 兆元 (350,000 億元)
    max_vol_limit = 16000000.0 # 用於正規化背景成交量的最大值
    
    # 繪製 Y 軸網格線與左/右 Y 軸刻度
    for i in range(6):
        pct = i / 5.0
        val_left = pct * max_y_left
        val_right_trillion = pct * 35.0  # 換算成兆元 (35兆)
        y_pos = margin_top + chart_h - pct * chart_h
        
        # 網格水平線
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y_pos}" x2="{W - margin_right}" y2="{y_pos}" stroke="#f1f5f9" stroke-width="1.5"/>')
        
        # 左 Y 軸標籤 (股價點數)
        svg_parts.append(f'  <text x="{margin_left - 12}" y="{y_pos + 4}" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="#475569" text-anchor="end">{int(val_left):,} 點</text>')
        
        # 右 Y 軸標籤 (M1B 兆元)
        svg_parts.append(f'  <text x="{W - margin_right + 12}" y="{y_pos + 4}" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="#475569" text-anchor="start">{val_right_trillion:.1f} 兆</text>')
    
    # Y 軸標題
    svg_parts.append(f'  <text x="{margin_left - 15}" y="{margin_top - 15}" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="bold" fill="#2563eb" text-anchor="end">← 每日加權指數 (點)</text>')
    svg_parts.append(f'  <text x="{W - margin_right + 15}" y="{margin_top - 15}" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="bold" fill="#059669" text-anchor="start">M1B 貨幣供給 (兆元) →</text>')
    
    # 6. 繪製成交量區域圖 (背景裝飾用，無右軸刻度) - 放在最底層
    vol_height = 0.18 * chart_h
    vol_points = []
    vol_points.append(f"{margin_left:.1f},{margin_top + chart_h:.1f}")
    for i in range(len(df)):
        vol_val = float(df.iloc[i]["Volume"])
        x = margin_left + (i / (len(df) - 1)) * chart_w
        y = margin_top + chart_h - (vol_val / max_vol_limit) * vol_height
        vol_points.append(f"{x:.1f},{y:.1f}")
    vol_points.append(f"{margin_left + chart_w:.1f},{margin_top + chart_h:.1f}")
    svg_parts.append(f'  <path d="M {" ".join(vol_points)} Z" fill="#94a3b8" opacity="0.25"/>')

    # 7. 繪製 M1B 歷史走勢折線 (右 Y 軸) - 翠綠色虛線
    m1b_path_points = []
    for i in range(len(df)):
        m1b_val = float(df.iloc[i]["M1B"])
        x = margin_left + (i / (len(df) - 1)) * chart_w
        y = margin_top + chart_h - (m1b_val / max_y_right) * chart_h
        m1b_path_points.append(f"{x:.1f},{y:.1f}")
    svg_parts.append(f'  <path d="M {m1b_path_points[0]} {" ".join("L " + p for p in m1b_path_points[1:])}" fill="none" stroke="#10b981" stroke-width="1.8" stroke-dasharray="4 2" opacity="0.85" stroke-linejoin="round"/>')

    # 8. 繪製每日指數折線圖 (左 Y 軸) - 藍色實線
    path_points = []
    for i in range(len(df)):
        close_val = float(df.iloc[i]["Close"])
        x = margin_left + (i / (len(df) - 1)) * chart_w
        y = margin_top + chart_h - (close_val / max_y_left) * chart_h
        path_points.append(f"{x:.1f},{y:.1f}")
    svg_parts.append(f'  <path d="M {path_points[0]} {" ".join("L " + p for p in path_points[1:])}" fill="none" stroke="#2563eb" stroke-width="1.3" opacity="0.9"/>')

    # 9. 處理與繪製歷史高點標註點
    annotated_points = []
    for item in data:
        precise_date = item.get("precise_date")
        if not precise_date:
            continue
            
        target_dt = pd.to_datetime(precise_date)
        if target_dt < df.index[0]:
            continue  # 略過所選開始日期之前的波段
            
        idx = abs(df.index - target_dt).argmin()
        close_val = float(df.iloc[idx]["Close"])
        
        x_pos = margin_left + (idx / (len(df) - 1)) * chart_w
        y_pos = margin_top + chart_h - (close_val / max_y_left) * chart_h
        
        annotated_points.append({
            "x": x_pos,
            "y": y_pos,
            "date": precise_date,
            "pts": item["peak_pts"],
            "vol": item["max_vol"],
            "jl_type": item["jl_type"],
            "real_type": item["type"],
        })
        
    # 繪製標註的指示虛線、圓圈與半透明文字膠囊
    for idx, pt in enumerate(annotated_points):
        color = colors.get(pt["real_type"], "#475569")
        x = pt["x"]
        y = pt["y"]
        
        # 指示垂直線
        svg_parts.append(f'  <line x1="{x}" y1="{y}" x2="{x}" y2="{margin_top + chart_h}" stroke="#cbd5e1" stroke-width="1.0" stroke-dasharray="3 3"/>')
        
        # 指示圓圈
        svg_parts.append(f'  <circle cx="{x}" cy="{y}" r="5.5" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>')
        
        # 決定文字排列在點的上方還是下方 (避開頂部與重疊)
        display_year = pt["date"].split("-")[0]
        
        # 繪製白色文字遮罩背景 (Badge)
        bg_w, bg_h = 56, 32
        bg_x = x - bg_w / 2
        bg_y = (y - 36) if y > margin_top + 50 else (y + 4)
        svg_parts.append(f'  <rect x="{bg_x}" y="{bg_y}" width="{bg_w}" height="{bg_h}" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="0.5" opacity="0.9"/>')
        
        if y > margin_top + 50:
            # 文字置於上方
            svg_parts.append(f'  <text x="{x}" y="{y - 27}" font-family="system-ui, -apple-system, sans-serif" font-size="8.5" font-weight="bold" fill="#0f172a" text-anchor="middle">{display_year}</text>')
            svg_parts.append(f'  <text x="{x}" y="{y - 17}" font-family="system-ui, -apple-system, sans-serif" font-size="8" fill="#475569" text-anchor="middle">{pt["jl_type"]}</text>')
            svg_parts.append(f'  <text x="{x}" y="{y - 7}" font-family="system-ui, -apple-system, sans-serif" font-size="8.5" font-weight="bold" fill="{color}" text-anchor="middle">{pt["real_type"]}</text>')
        else:
            # 文字置於下方
            svg_parts.append(f'  <text x="{x}" y="{y + 13}" font-family="system-ui, -apple-system, sans-serif" font-size="8.5" font-weight="bold" fill="#0f172a" text-anchor="middle">{display_year}</text>')
            svg_parts.append(f'  <text x="{x}" y="{y + 23}" font-family="system-ui, -apple-system, sans-serif" font-size="8" fill="#475569" text-anchor="middle">{pt["jl_type"]}</text>')
            svg_parts.append(f'  <text x="{x}" y="{y + 33}" font-family="system-ui, -apple-system, sans-serif" font-size="8.5" font-weight="bold" fill="{color}" text-anchor="middle">{pt["real_type"]}</text>')

    # 10. 繪製 X 軸刻度與年份標籤 (依據時間長度動態調整年份間距步長)
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top + chart_h}" x2="{W - margin_right}" y2="{margin_top + chart_h}" stroke="#cbd5e1" stroke-width="1.5"/>')
    
    start_year = int(start_date.split("-")[0])
    span = 2026 - start_year
    
    # 依時間跨度決定年份間距
    if span <= 7:
        step = 1  # 跨度小於 7 年 (例如 2020 起)，每年標記一次
    elif span <= 15:
        step = 2  # 跨度小於 15 年，每 2 年標記一次
    else:
        step = 3  # 跨度較長，每 3 年標記一次
        
    years_to_show = range(start_year, 2027, step)
    for yr in years_to_show:
        yr_indices = [idx for idx, date in enumerate(df.index) if date.year == yr]
        if yr_indices:
            idx_pos = yr_indices[0]
            x = margin_left + (idx_pos / (len(df) - 1)) * chart_w
            svg_parts.append(f'  <line x1="{x}" y1="{margin_top + chart_h}" x2="{x}" y2="{margin_top + chart_h + 5}" stroke="#cbd5e1" stroke-width="1.0"/>')
            svg_parts.append(f'  <text x="{x}" y="{margin_top + chart_h + 18}" font-family="system-ui, -apple-system, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">{yr}</text>')
            
    # 11. 繪製底部圖例 (Legend)
    legend_y = H - 25
    
    # 指標線圖例
    svg_parts.append(f'  <line x1="{margin_left}" y1="{legend_y - 4}" x2="{margin_left + 25}" y2="{legend_y - 4}" stroke="#2563eb" stroke-width="2.5"/>')
    svg_parts.append(f'  <text x="{margin_left + 30}" y="{legend_y}" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="#475569" font-weight="bold">加權股價指數 (左軸)</text>')
    
    svg_parts.append(f'  <line x1="{margin_left + 160}" y1="{legend_y - 4}" x2="{margin_left + 185}" y2="{legend_y - 4}" stroke="#10b981" stroke-width="2" stroke-dasharray="3 1"/>')
    svg_parts.append(f'  <text x="{margin_left + 190}" y="{legend_y}" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="#475569" font-weight="bold">M1B 資金活水 (右軸)</text>')
    
    svg_parts.append(f'  <rect x="{margin_left + 325}" y="{legend_y - 10}" width="20" height="10" fill="#94a3b8" opacity="0.3"/>')
    svg_parts.append(f'  <text x="{margin_left + 350}" y="{legend_y}" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="#475569" font-weight="bold">背景: 每日成交量</text>')
    
    # 實質風險顏色圖例
    legends = [
        ("大漲", colors["大漲"]),
        ("大跌", colors["大跌"]),
        ("中漲", colors["中漲"]),
        ("中跌", colors["中跌"]),
    ]
    legend_start_x = W - margin_right - 250
    for idx, (lbl, col) in enumerate(legends):
        lx = legend_start_x + idx * 65
        svg_parts.append(f'  <rect x="{lx}" y="{legend_y - 10}" width="8" height="8" rx="1.5" fill="{col}"/>')
        svg_parts.append(f'  <text x="{lx + 12}" y="{legend_y}" font-family="system-ui, -apple-system, sans-serif" font-size="10.5" fill="#475569" font-weight="bold">{lbl}</text>')
        
    svg_parts.append('</svg>')
    return "\n".join(svg_parts)

def process_group(rows: list[dict]) -> dict:
    subtotal_row = None
    for r in rows:
        if r["is_subtotal"] == "True":
            subtotal_row = r
            break
            
    twse_row = None
    for r in rows:
        if r["market"] == "上市":
            twse_row = r
            break
    if not twse_row:
        twse_row = rows[0]
        
    # 取得點數 (peak_pts)
    peak_pts_val = 0.0
    if twse_row.get("peak_pts"):
        try:
            peak_pts_val = float(twse_row["peak_pts"])
        except ValueError:
            pass
            
    # 取得成交量 (max_vol)
    max_vol_val = 0.0
    vol_row = subtotal_row if subtotal_row else twse_row
    if vol_row.get("max_vol"):
        try:
            max_vol_val = float(vol_row["max_vol"])
        except ValueError:
            pass

    # 取得比重
    ratio_row = subtotal_row if subtotal_row else twse_row
    ratio_val = 0.0
    if ratio_row.get("ratio"):
        try:
            ratio_val = float(ratio_row["ratio"])
        except ValueError:
            pass
        
    date_val = subtotal_row["peak_date"] if subtotal_row else twse_row["peak_date"].replace(".", "/")
    precise_date = twse_row["peak_date"].replace(".", "-")

    return {
        "date": date_val,
        "precise_date": precise_date,
        "ratio": ratio_val,
        "type": twse_row["type"],
        "jl_type": twse_row["jl_type"],
        "peak_pts": peak_pts_val,
        "max_vol": max_vol_val
    }

def main():
    csv_path = "m1b_peak_result.csv"
    if not os.path.exists(csv_path):
        print(f"找不到 {csv_path}，請確認是否已生成！")
        return
        
    # 定義圖表時間跨度
    charts_config = [
        ("1997-07-02", "m1b_peak_chart.svg"),
        ("2000-01-01", "m1b_peak_chart_2000.svg"),
        ("2015-01-01", "m1b_peak_chart_2015.svg"),
        ("2020-01-01", "m1b_peak_chart_2020.svg")
    ]
    
    for start_date, filename in charts_config:
        svg_content = generate_svg(csv_path, start_date=start_date)
        
        # 輸出到當前目錄 (TaiwanBank)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"成功生成圖表：{filename}")
        
        # 輸出到 mkdocs-investment 副本目錄
        dest_path = f"../mkdocs-investment/docs/{filename}"
        if os.path.exists("../mkdocs-investment/docs"):
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            print(f"成功同步至：{dest_path}")

if __name__ == "__main__":
    main()
