import os
import time
import json
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta

API_KEY = os.environ.get("MASSIVE_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "market_data.parquet"

def get_last_trading_day():
    today = datetime.utcnow()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")

def get_active_us_tickers():
    """מושך את רשימת כל המניות הסחירות בארה\"ב (מעל $5 ומעל 400 אלף נפח) בקריאה אחת מ-Massive"""
    for days_back in range(5):
        check_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{check_date}?adjusted=true&apiKey={API_KEY}"
        res = requests.get(url).json()
        if "results" in res and len(res["results"]) > 1000:
            tickers = [
                bar["T"] for bar in res["results"]
                if bar.get("T") and bar["T"].isalpha() and len(bar["T"]) <= 5
                and bar.get("c", 0) >= 5.0 and bar.get("v", 0) >= 400000
            ]
            print(f"נמצאו {len(tickers)} מניות סחירות בארה\"ב נכון לתאריך {check_date}.")
            return sorted(list(set(tickers)))
    return ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "GOOGL", "PLTR", "COIN"]

def bootstrap_history_fast():
    """מאתחל שנה אחורה לכל המניות הסחירות בבאצ'ים מהירים"""
    tickers = get_active_us_tickers()
    print(f"מתחיל אתחול היסטוריה עבור {len(tickers)} מניות...")
    all_rows = []
    batch_size = 250
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        print(f"מוריד קבוצה {i//batch_size + 1} מתוך {(len(tickers)-1)//batch_size + 1}...")
        data = yf.download(batch, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
        
        for t in batch:
            try:
                if len(batch) == 1:
                    sub = data
                elif t in data.columns.get_level_values(0):
                    sub = data[t]
                else:
                    continue
                sub = sub.dropna(subset=["Close"])
                for dt, row in sub.iterrows():
                    all_rows.append({
                        "Ticker": t,
                        "Date": dt.strftime("%Y-%m-%d"),
                        "Open": round(float(row["Open"]), 4),
                        "High": round(float(row["High"]), 4),
                        "Low": round(float(row["Low"]), 4),
                        "Close": round(float(row["Close"]), 4),
                        "Volume": int(row["Volume"])
                    })
            except Exception:
                continue
        time.sleep(1)

    df = pd.DataFrame(all_rows)
    df.to_parquet(DATA_FILE, index=False)
    print(f"האתחול הושלם בהצלחה! נשמרו {len(df)} שורות.")
    return df

def update_daily_grouped(df):
    """מעדכן את כל אלפי המניות בקריאת API אחת בלבד דרך Massive"""
    target_date = get_last_trading_day()
    if target_date in df["Date"].values:
        print(f"הנתונים עבור {target_date} כבר מעודכנים.")
        return df

    print(f"מושך נתוני סוף יום לכל הבורסה מ-Massive עבור {target_date}...")
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{target_date}?adjusted=true&apiKey={API_KEY}"
    res = requests.get(url).json()
    
    if "results" not in res:
        print("לא נמצאו נתונים חדשים מ-Massive (חג או שהמסחר טרם נסגר).")
        return df

    existing_tickers = set(df["Ticker"].unique())
    new_rows = []
    for bar in res["results"]:
        t = bar.get("T")
        if t and t.isalpha() and len(t) <= 5:
            if t in existing_tickers or (bar.get("c", 0) >= 5.0 and bar.get("v", 0) >= 400000):
                new_rows.append({
                    "Ticker": t,
                    "Date": target_date,
                    "Open": bar["o"],
                    "High": bar["h"],
                    "Low": bar["l"],
                    "Close": bar["c"],
                    "Volume": bar["v"]
                })

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df.drop_duplicates(subset=["Ticker", "Date"], keep="last", inplace=True)
        df = df.sort_values("Date").groupby("Ticker").tail(250).reset_index(drop=True)
        df.to_parquet(DATA_FILE, index=False)
        print(f"עודכנו {len(new_rows)} מניות.")
    return df

def calculate_indicators(sub_df):
    sub_df = sub_df.sort_values("Date").copy()
    sub_df["SMA200"] = sub_df["Close"].rolling(200).mean()
    sub_df["Vol_SMA20"] = sub_df["Volume"].rolling(20).mean()
    sub_df["Rel_Vol"] = sub_df["Volume"] / sub_df["Vol_SMA20"]
    
    high_low = sub_df["High"] - sub_df["Low"]
    high_close = np.abs(sub_df["High"] - sub_df["Close"].shift())
    low_close = np.abs(sub_df["Low"] - sub_df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    sub_df["ATR_Pct"] = (tr.rolling(14).mean() / sub_df["Close"]) * 100
    return sub_df

def check_patterns_and_alert(ticker, sub_df):
    if len(sub_df) < 60:
        return
    
    recent = sub_df.tail(85).reset_index(drop=True)
    curr = recent.iloc[-1]
    prev = recent.iloc[-2]
    
    # סינון נפח יחסי ומינימום מחיר
    if curr["Rel_Vol"] < 1.2 or curr["Close"] < 5.0:
        return

    # 1. תבנית פריצת קו מגמה יורד (עד 85 נרות אחורה)
    search_window = recent.iloc[:-10]
    peak_idx = search_window["High"].idxmax()
    peak_price = recent.loc[peak_idx, "High"]
    
    mid_df = recent.iloc[peak_idx+4:-2]
    if len(mid_df) >= 3:
        best_slope = -999
        for idx, row in mid_df.iterrows():
            s = (row["High"] - peak_price) / (idx - peak_idx)
            if s < 0 and s > best_slope:
                best_slope = s
                
        if best_slope > -999:
            curr_idx = len(recent) - 1
            trend_resistance = peak_price + best_slope * (curr_idx - peak_idx)
            prev_resistance = peak_price + best_slope * (curr_idx - 1 - peak_idx)
            
            if prev["Close"] <= prev_resistance and curr["Close"] > trend_resistance:
                drop_pct = ((curr["Close"] - peak_price) / peak_price) * 100
                bars_count = curr_idx - peak_idx
                stop_lvl = recent.iloc[-5:]["Low"].min()
                
                send_alert(
                    ticker=ticker,
                    pattern_he="פריצת קו מגמה יורד",
                    pattern_en="DESCENDING TRENDLINE",
                    badge_title="Descending Trendline Breakout",
                    sub_df=sub_df.tail(140),
                    resistance=trend_resistance,
                    support=stop_lvl,
                    target=peak_price,
                    extra_label="Trend Drop",
                    extra_val=f"{drop_pct:.1f}%   •   {bars_count} bars",
                    trend_start=(peak_idx, peak_price),
                    trend_end=(curr_idx, trend_resistance)
                )
                return

    # 2. תבנית פריצת מלבן / Darvas Box (28 נרות אחרונים)
    box_df = recent.iloc[-29:-1]
    box_high = box_df["High"].max()
    box_low = box_df["Low"].min()
    box_range_pct = ((box_high - box_low) / box_low) * 100
    
    if box_range_pct <= 18.0 and prev["Close"] <= box_high and curr["Close"] > box_high:
        stop_lvl = recent.iloc[-5:]["Low"].min()
        target_lvl = curr["Close"] + (box_high - box_low)
        send_alert(
            ticker=ticker,
            pattern_he="פריצת מלבן / דרווס בוקס",
            pattern_en="RECTANGLE / DARVAS BOX",
            badge_title="Darvas Box Breakout",
            sub_df=sub_df.tail(140),
            resistance=box_high,
            support=stop_lvl,
            target=target_lvl,
            extra_label="Box Range",
            extra_val=f"{box_range_pct:.1f}%   •   28 bars",
            trend_start=None,
            trend_end=None
        )

def generate_modern_chart(ticker, plot_df, resistance, support, badge_title, trend_start, trend_end):
    """מצייר כרטיס גרף מודרני ונקי בסגנון Strat Ninja"""
    plot_df = plot_df.reset_index(drop=True)
    n = len(plot_df)
    
    curr = plot_df.iloc[-1]
    prev = plot_df.iloc[-2]
    price = curr["Close"]
    chg_pct = ((price - prev["Close"]) / prev["Close"]) * 100
    
    # צבעים
    bg_outer = "#12131a"
    bg_inner = "#0c0d12"
    green_c = "#22c55e"
    red_c = "#ef4444"
    grid_c = "#1e202b"
    text_muted = "#71717a"
    
    fig = plt.figure(figsize=(11, 6.8), facecolor=bg_outer)
    
    # כותרת עליונה (Header)
    fig.text(0.055, 0.925, "MARKET SCANNER", color=text_muted, fontsize=9, fontweight="bold", family="sans-serif")
    fig.text(0.055, 0.875, ticker, color="#ffffff", fontsize=22, fontweight="bold", family="sans-serif")
    fig.text(0.135, 0.878, "Daily", color="#a78bfa", fontsize=12, fontweight="bold", family="sans-serif")
    
    fig.text(0.055, 0.825, f"${price:.2f}", color="#ffffff", fontsize=19, fontweight="bold", family="sans-serif")
    badge_bg = "#143824" if chg_pct >= 0 else "#3f1518"
    badge_fg = green_c if chg_pct >= 0 else red_c
    sign = "+" if chg_pct >= 0 else ""
    fig.text(0.155, 0.830, f" {sign}{chg_pct:.2f}% ", color=badge_fg, fontsize=10.5, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.35", facecolor=badge_bg, edgecolor="none"))

    # תגית התבנית בצד ימין למעלה
    fig.text(0.945, 0.895, f" 📊 {badge_title} ", color="#e4e4e7", fontsize=10, fontweight="bold", ha="right",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1c26", edgecolor="#2e3142", linewidth=1))

    # אזור הגרף המרכזי
    ax = fig.add_axes([0.055, 0.14, 0.89, 0.64], facecolor=bg_inner)
    
    # הסרת מסגרות חיצוניות והעברת ציר המחירים לימין
    for spine in ["top", "left", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#27272a")
    ax.yaxis.tick_right()
    ax.tick_params(axis="y", colors=text_muted, labelsize=9, length=0, pad=8)
    ax.tick_params(axis="x", colors=text_muted, labelsize=8.5, length=4)
    ax.grid(True, color=grid_c, linestyle="--", linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)

    # חישוב גבולות ציר Y (כולל מקום לתגיות תמיכה/התנגדות ולנפח)
    all_highs = plot_df["High"].max()
    all_lows = plot_df["Low"].min()
    y_max = max(all_highs, resistance) * 1.03
    y_min = min(all_lows, support) * 0.94
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(-3, n + 2)

    # ציור נרות יפניים
    for i, row in plot_df.iterrows():
        c = green_c if row["Close"] >= row["Open"] else red_c
        ax.plot([i, i], [row["Low"], row["High"]], color=c, linewidth=1.1, zorder=3)
        body_min = min(row["Open"], row["Close"])
        body_h = max(abs(row["Close"] - row["Open"]), (y_max - y_min) * 0.002)
        rect = patches.Rectangle((i - 0.32, body_min), 0.64, body_h, facecolor=c, edgecolor=c, zorder=4)
        ax.add_patch(rect)

    # ציור נפח מסחר שקוף בתחתית הגרף (Overlay)
    ax_vol = ax.twinx()
    ax_vol.set_ylim(0, plot_df["Volume"].max() * 4.8)
    ax_vol.axis("off")
    vol_colors = [green_c if plot_df.loc[i, "Close"] >= plot_df.loc[i, "Open"] else red_c for i in range(n)]
    ax_vol.bar(range(n), plot_df["Volume"], color=vol_colors, alpha=0.25, width=0.65, zorder=1)

    # ציור קו התנגדות / קו מגמה יורד (אדום מקווקו)
    if trend_start and trend_end:
        offset = n - 85
        x1 = max(0, trend_start[0] + offset)
        x2 = trend_end[0] + offset
        ax.plot([x1, x2], [trend_start[1], trend_end[1]], color=red_c, linestyle="--", linewidth=1.3, alpha=0.9, zorder=5)
    else:
        ax.axhline(resistance, color=red_c, linestyle="--", linewidth=1.1, alpha=0.8, zorder=5)

    # ציור קווי תמיכה והתנגדות אופקיים + תגיות צבעוניות משמאל (R ו-S)
    r_mid = resistance * 1.018
    s_low = support * 0.982
    
    levels = [
        (r_mid, f"R {r_mid:.2f}", red_c, "#3f1518"),
        (resistance, f"R {resistance:.2f}", red_c, "#3f1518"),
        (support, f"S {support:.2f}", green_c, "#143824"),
        (s_low, f"S {s_low:.2f}", green_c, "#143824")
    ]
    
    for lvl_price, label_txt, fg_c, bg_c in levels:
        ax.axhline(lvl_price, color=fg_c, linestyle="--", linewidth=0.85, alpha=0.55, zorder=2)
        ax.text(0.5, lvl_price, f" {label_txt} ", color=fg_c, fontsize=8, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=bg_c, edgecolor=fg_c, linewidth=0.8), zorder=6)

    # תאריכים בציר X
    tick_indices = np.linspace(5, n - 1, 6, dtype=int)
    tick_labels = [datetime.strptime(plot_df.loc[idx, "Date"], "%Y-%m-%d").strftime("%b %d") for idx in tick_indices]
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels)

    # שורת קרדיט תחתונה (Footer)
    fig.text(0.5, 0.045, f"MARKET SCANNER  •  POWERED BY MASSIVE API  •  {curr['Date']} IL",
             color="#52525b", fontsize=8.5, ha="center", fontweight="bold")

    plt.savefig("chart.png", dpi=160, facecolor=bg_outer)
    plt.close(fig)

def send_alert(ticker, pattern_he, pattern_en, badge_title, sub_df, resistance, support, target, extra_label, extra_val, trend_start, trend_end):
    curr = sub_df.iloc[-1]
    price = curr["Close"]
    pct_above = ((price - resistance) / resistance) * 100
    rel_vol = curr["Rel_Vol"]
    atr = curr["ATR_Pct"]
    vs_200ma = "above ✅" if pd.notna(curr["SMA200"]) and price > curr["SMA200"] else "below ❌"
    
    stop = support
    if target <= price:
        target = price + (price - stop) * 2.5
    stop_pct = ((stop - price) / price) * 100
    target_pct = ((target - price) / price) * 100
    rr = abs((target - price) / (price - stop)) if price > stop else 0

    generate_modern_chart(ticker, sub_df, resistance, support, badge_title, trend_start, trend_end)

    table_text = f"""```
{pattern_en:<25} •   Daily
────────────────────────────────────────
Price          ${price:.2f}
Resistance     {resistance:.2f}   ▲ +{pct_above:.2f}%
Rel Volume     {rel_vol:.2f}x
ATR (Daily)    {atr:.2f}%   🟡
{extra_label:<14} {extra_val}
vs 200MA       {vs_200ma}
Entry          {price:.2f}
Stop           {stop:.2f}   ({stop_pct:.1f}%)
Target         {target:.2f}   (+{target_pct:.1f}%)
R : R          {rr:.2f}
```"""

    payload = {
        "embeds": [
            {
                "title": f"🐍 {ticker} — {pattern_he} • Daily",
                "description": f"**{ticker} פרץ תבנית {pattern_he} מעל התנגדות {resistance:.2f}**
{table_text}
[📊 פתח ב-TradingView](https://www.tradingview.com/chart/?symbol={ticker})",
                "color": 2278750,
                "image": {"url": "attachment://chart.png"},
                "footer": {"text": f"Massive Market Scanner • {curr['Date']} IL"}
            }
        ]
    }

    with open("chart.png", "rb") as f:
        files = {
            "payload_json": (None, json.dumps(payload)),
            "files": ("chart.png", f, "image/png")
        }
        requests.post(WEBHOOK_URL, files=files)
        print(f"נשלחה התראה לדיסקורד עבור {ticker}!")
        time.sleep(2.5)

if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        df = bootstrap_history_fast()
    else:
        df = pd.read_parquet(DATA_FILE)
        df = update_daily_grouped(df)

    tickers = df["Ticker"].unique()
    print(f"סורק {len(tickers)} מניות לאיתור תבניות פריצה...")
    for ticker in tickers:
        sub = df[df["Ticker"] == ticker]
        if len(sub) >= 60:
            sub = calculate_indicators(sub)
            check_patterns_and_alert(ticker, sub)
