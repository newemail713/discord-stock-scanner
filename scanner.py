import os
import time
import json
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from datetime import datetime, timedelta

API_KEY = os.environ.get("MASSIVE_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

DATA_FILE = "market_data.parquet"
MCAP_CACHE_FILE = "market_caps.json"
MIN_MARKET_CAP = 2_000_000_000  # 2 מיליארד דולר
MIN_ATR_PCT = 1.0               # ATR יומי גדול מ-1%

def get_last_trading_day():
    today = datetime.utcnow()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")

def load_market_caps():
    if os.path.exists(MCAP_CACHE_FILE):
        try:
            with open(MCAP_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_market_caps(mcaps):
    with open(MCAP_CACHE_FILE, "w") as f:
        json.dump(mcaps, f)

def get_market_cap(ticker, mcaps_cache):
    """בודק שווי שוק ושומר במטמון כדי שהסריקה תרוץ תוך שניות"""
    if ticker in mcaps_cache:
        return mcaps_cache[ticker]
    try:
        yf_t = ticker.replace(".", "-")
        info = yf.Ticker(yf_t).fast_info
        mcap = getattr(info, "market_cap", None)
        if mcap is not None:
            mcaps_cache[ticker] = float(mcap)
            return float(mcap)
    except Exception:
        pass
    mcaps_cache[ticker] = 0.0
    return 0.0

def get_active_us_tickers():
    """מושך את כל המניות הפעילות והסחירות בארה"ב בקריאה אחת מול Massive"""
    for days_back in range(0, 6):
        check_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{check_date}?adjusted=true&apiKey={API_KEY}"
        res = requests.get(url).json()
        if "results" in res and len(res["results"]) > 1000:
            tickers = []
            for bar in res["results"]:
                t = bar.get("T", "")
                if t.isalpha() and len(t) <= 5 and bar.get("c", 0) >= 5.0 and bar.get("v", 0) >= 400000:
                    tickers.append(t)
            return sorted(list(set(tickers)))
    return ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "GOOGL", "KLAR", "PLTR", "COIN"]

def bootstrap_history_fast():
    tickers = get_active_us_tickers()
    print(f"מאתחל היסטוריה עבור {len(tickers)} מניות סחירות בארה\"ב...")
    all_rows = []
    chunk_size = 250
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        data = yf.download(chunk, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
        for t in chunk:
            try:
                sub = data[t].dropna(subset=["Close"]) if len(chunk) > 1 else data.dropna(subset=["Close"])
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
    df = pd.DataFrame(all_rows)
    df.to_parquet(DATA_FILE, index=False)
    return df

def update_daily_grouped(df):
    target_date = get_last_trading_day()
    if target_date in df["Date"].values:
        return df

    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{target_date}?adjusted=true&apiKey={API_KEY}"
    res = requests.get(url).json()
    if "results" not in res:
        return df

    existing_tickers = set(df["Ticker"].unique())
    new_rows = []
    for bar in res["results"]:
        t = bar.get("T", "")
        if t in existing_tickers or (t.isalpha() and len(t) <= 5 and bar.get("c", 0) >= 5.0 and bar.get("v", 0) >= 400000):
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
        df = df.sort_values("Date").groupby("Ticker").tail(220).reset_index(drop=True)
        df.to_parquet(DATA_FILE, index=False)
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

def generate_modern_chart(ticker, plot_df, pattern_en, resistance, support, stop, target, trend_coords=None):
    plot_df = plot_df.reset_index(drop=True).copy()
    n = len(plot_df)
    curr = plot_df.iloc[-1]
    prev = plot_df.iloc[-2]
    daily_chg = ((curr["Close"] - prev["Close"]) / prev["Close"]) * 100

    fig = plt.figure(figsize=(11, 7.2), facecolor="#0b0e14")
    ax = fig.add_axes([0.04, 0.10, 0.88, 0.72], facecolor="#0f131a")

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.grid(True, color="#1c222e", linestyle="-", linewidth=0.7)
    ax.set_axisbelow(True)

    # כותרת עליונה בסגנון Strat Ninja
    fig.text(0.04, 0.935, "MASSIVE SCANNER", color="#7e8899", fontsize=9, fontweight="bold")
    fig.text(0.04, 0.892, ticker, color="#ffffff", fontsize=22, fontweight="bold")
    fig.text(0.04 + len(ticker)*0.022, 0.895, "Daily", color="#6d78c9", fontsize=12, fontweight="bold")

    price_str = f"${curr['Close']:.2f}"
    fig.text(0.04, 0.848, price_str, color="#ffffff", fontsize=16, fontweight="bold")

    chg_color = "#26a69a" if daily_chg >= 0 else "#ef5350"
    chg_bg = "#132e2b" if daily_chg >= 0 else "#33191c"
    chg_sign = "+" if daily_chg >= 0 else ""
    fig.text(
        0.04 + len(price_str)*0.0155, 0.851, f" {chg_sign}{daily_chg:.2f}% ",
        color=chg_color, fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=chg_bg, edgecolor="none")
    )

    # תגית שם התבנית בצד ימין למעלה
    fig.text(
        0.92, 0.90, f"  {pattern_en.title()} Breakout  ",
        color="#e0e6f0", fontsize=10.5, fontweight="bold", ha="right",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#171c26", edgecolor="#2a3242", linewidth=1)
    )

    # ציור נרות יפניים
    for i, row in plot_df.iterrows():
        c = "#26a69a" if row["Close"] >= row["Open"] else "#ef5350"
        ax.plot([i, i], [row["Low"], row["High"]], color=c, linewidth=1.0, zorder=3)
        body_bottom = min(row["Open"], row["Close"])
        body_height = max(abs(row["Close"] - row["Open"]), (plot_df["High"].max() - plot_df["Low"].min()) * 0.002)
        rect = Rectangle((i - 0.32, body_bottom), 0.64, body_height, facecolor=c, edgecolor=c, zorder=4)
        ax.add_patch(rect)

    # נפח מסחר שקוף בתחתית הגרף (Overlay)
    ax_vol = ax.twinx()
    ax_vol.set_ylim(0, plot_df["Volume"].max() * 4.5)
    ax_vol.axis("off")
    vol_colors = ["#1b4d47" if r["Close"] >= r["Open"] else "#522226" for _, r in plot_df.iterrows()]
    ax_vol.bar(range(n), plot_df["Volume"], color=vol_colors, width=0.6, alpha=0.55, zorder=1)

    # קווי תמיכה והתנגדות אופקיים + תגיות R ו-S משמאל
    levels = [
        ("R", resistance, "#ef5350", "#2e161b"),
        ("S", support, "#26a69a", "#122b28"),
        ("S", stop, "#26a69a", "#122b28"),
    ]
    used_y = []
    y_span = plot_df["High"].max() - plot_df["Low"].min()

    for label, lvl, col, bg_col in levels:
        ax.axhline(lvl, color=col, linestyle="--", linewidth=0.9, alpha=0.75, zorder=2)
        display_y = lvl
        for uy in used_y:
            if abs(display_y - uy) < y_span * 0.045:
                display_y -= y_span * 0.048
        used_y.append(display_y)
        ax.text(
            1.5, display_y, f" {label} {lvl:.2f} ",
            color=col, fontsize=8.5, fontweight="bold", va="center", ha="left", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=bg_col, edgecolor=col, linewidth=0.8)
        )

    # קו מגמה יורד (אם רלוונטי)
    if trend_coords:
        (x1, y1), (x2, y2) = trend_coords
        ax.plot([x1, x2], [y1, y2], color="#ef5350", linestyle="--", linewidth=1.3, zorder=5)

    # עיצוב צירים ותאריכים
    ax.yaxis.tick_right()
    ax.tick_params(axis="y", colors="#6e7787", labelsize=9, length=0)
    ax.set_xlim(-1, n + 2)

    y_min = min(plot_df["Low"].min(), stop) * 0.96
    y_max = max(plot_df["High"].max(), resistance) * 1.03
    ax.set_ylim(y_min, y_max)

    tick_indices = np.linspace(4, n - 5, 6, dtype=int)
    tick_labels = [datetime.strptime(plot_df.loc[idx, "Date"], "%Y-%m-%d").strftime("%b %d") for idx in tick_indices]
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels, color="#6e7787", fontsize=9)
    ax.tick_params(axis="x", length=0, pad=8)

    # שורת קרדיט תחתונה
    fig.text(
        0.5, 0.03,
        f"MASSIVE SCANNER  •  POWERED BY POLYGON.IO  •  {curr['Date']} IL",
        color="#555e6e", fontsize=8.5, ha="center", fontweight="bold"
    )

    plt.savefig("chart.png", dpi=160, facecolor="#0b0e14")
    plt.close(fig)

def format_mcap(mcap):
    if mcap >= 1e12:
        return f"${mcap/1e12:.2f}T"
    return f"${mcap/1e9:.1f}B"

def check_patterns_and_alert(ticker, sub_df, mcaps_cache):
    if len(sub_df) < 85:
        return

    recent = sub_df.tail(85).reset_index(drop=True)
    curr = recent.iloc[-1]
    prev = recent.iloc[-2]

    # סינון 1: נפח מסחר יחסי ו-ATR יומי גדול מ-1%
    if curr["Rel_Vol"] < 1.15 or pd.isna(curr["ATR_Pct"]) or curr["ATR_Pct"] <= MIN_ATR_PCT:
        return

    # סינון 2: שווי שוק מעל 2 מיליארד דולר
    mcap = get_market_cap(ticker, mcaps_cache)
    if mcap < MIN_MARKET_CAP:
        return

    # תבנית 1: פריצת קו מגמה יורד (עד 85 נרות אחורה)
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
                support_lvl = recent.iloc[peak_idx:]["Low"].min()
                stop_lvl = recent.iloc[-6:-1]["Low"].min()
                if stop_lvl >= curr["Close"]:
                    stop_lvl = curr["Low"] * 0.98

                plot_df = sub_df.tail(120).reset_index(drop=True)
                offset = len(plot_df) - len(recent)
                trend_coords = [(peak_idx + offset, peak_price), (curr_idx + offset, trend_resistance)]

                send_alert(
                    ticker=ticker,
                    pattern_he="פריצת קו מגמה יורד",
                    pattern_en="DESCENDING TRENDLINE",
                    plot_df=plot_df,
                    resistance=trend_resistance,
                    support=support_lvl,
                    stop=stop_lvl,
                    target=peak_price,
                    mcap=mcap,
                    extra_label="Trend Drop",
                    extra_val=f"{drop_pct:.1f}%  •  {bars_count} bars",
                    trend_coords=trend_coords
                )
                return

    # תבנית 2: פריצת מלבן / Darvas Box (30 נרות אחרונים)
    box_df = recent.iloc[-31:-1]
    box_high = box_df["High"].max()
    box_low = box_df["Low"].min()
    box_range_pct = ((box_high - box_low) / box_low) * 100

    if box_range_pct <= 18.0 and prev["Close"] <= box_high and curr["Close"] > box_high:
        stop_lvl = recent.iloc[-6:-1]["Low"].min()
        if stop_lvl >= curr["Close"]:
            stop_lvl = box_low
        target_lvl = curr["Close"] + (box_high - box_low) * 1.5

        send_alert(
            ticker=ticker,
            pattern_he="פריצת מלבן / דרווס בוקס",
            pattern_en="RECTANGLE / DARVAS BOX",
            plot_df=sub_df.tail(120).reset_index(drop=True),
            resistance=box_high,
            support=box_low,
            stop=stop_lvl,
            target=target_lvl,
            mcap=mcap,
            extra_label="Box Range",
            extra_val=f"{box_range_pct:.1f}%  •  30 bars",
            trend_coords=None
        )

def send_alert(ticker, pattern_he, pattern_en, plot_df, resistance, support, stop, target, mcap, extra_label, extra_val, trend_coords):
    curr = plot_df.iloc[-1]
    price = curr["Close"]
    pct_above = ((price - resistance) / resistance) * 100
    rel_vol = curr["Rel_Vol"]
    atr = curr["ATR_Pct"]
    vs_200ma = "above ✓" if pd.notna(curr["SMA200"]) and price > curr["SMA200"] else "below ✗"

    stop_pct = ((stop - price) / price) * 100
    target_pct = ((target - price) / price) * 100
    rr = abs((target - price) / (price - stop)) if price != stop else 0
    atr_dot = "🟢" if atr < 3.0 else ("🟡" if atr < 5.5 else "🔴")

    generate_modern_chart(ticker, plot_df, pattern_en, resistance, support, stop, target, trend_coords)

    table_text = f"""```
{pattern_en:<24} •  Daily
──────────────────────────────────────
Price         ${price:.2f}
Market Cap    {format_mcap(mcap)}
Resistance    {resistance:.2f}   ▲ +{pct_above:.2f}%
Rel Volume    {rel_vol:.2f}×
ATR (Daily)   {atr:.2f}%  {atr_dot}
{extra_label:<13} {extra_val}
vs 200MA      {vs_200ma}
Entry         {price:.2f}
Stop          {stop:.2f}   ({stop_pct:.1f}%)
Target        {target:.2f}   (+{target_pct:.1f}%)
R : R         {rr:.2f}
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
        print(f"Alert sent to Discord for {ticker}!")
        time.sleep(2.5)

if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        df = bootstrap_history_fast()
    else:
        df = pd.read_parquet(DATA_FILE)
        df = update_daily_grouped(df)

    mcaps_cache = load_market_caps()

    for ticker, sub in df.groupby("Ticker"):
        sub = calculate_indicators(sub)
        check_patterns_and_alert(ticker, sub, mcaps_cache)

    save_market_caps(mcaps_cache)
