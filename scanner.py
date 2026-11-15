import os
import time
import json
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import mplfinance as mpf
from datetime import datetime, timedelta

API_KEY = os.environ.get("MASSIVE_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

WATCHLIST = [
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "AON", "AOS", "APA", "APD", "APH", "APO", "APP",
    "APTV", "ARE", "ARES", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP",
    "AZO", "BA", "BAC", "BALL", "BAX", "BBY", "BDX", "BE", "BEN", "BF.B",
    "BG", "BIIB", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BNY", "BR", "BRK.B",
    "BRO", "BSX", "BX", "BXP", "C", "CAG", "CAH", "CARR", "CASY", "CAT",
    "CB", "CBOE", "CBRE", "CCI", "CCL", "CDNS", "CDW", "CEG", "CF", "CFG",
    "CHD", "CHRW", "CHTR", "CI", "CIEN", "CINF", "CL", "CLX", "CMCSA", "CME",
    "CMG", "CMI", "CMS", "CNC", "CNP", "COF", "COHR", "COIN", "COO", "COP",
    "COR", "COST", "CPAY", "CPB", "CPRT", "CPT", "CRL", "CRM", "CRWD", "CSCO",
    "CSGP", "CSX", "CTAS", "CTSH", "CVS", "CVNA", "CVX", "D", "DAL", "DASH",
    "DD", "DDOG", "DE", "DECK", "DELL", "DG", "DGX", "DHI", "DHR", "DIS",
    "DLR", "DLTR", "DOC", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK", "DVA",
    "DVN", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EG", "EIX",
    "EL", "ELV", "EME", "EMR", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ERIE",
    "ES", "ESS", "ETN", "ETR", "EVRG", "EW", "EXC", "EXE", "EXPD", "EXPE",
    "EXR", "F", "FANG", "FAST", "FCX", "FDS", "FDX", "FE", "FERG",
    "FFIV", "FICO", "FIS", "FISV", "FITB", "FLEX", "FIX", "FOX", "FOXA", "FRT",
    "FSLR", "FTNT", "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD",
    "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN",
    "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD", "HIG", "HII", "HLT",
    "HOLX", "HON", "HOOD", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY",
    "HUBB", "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY",
    "INTC", "INTU", "INVH", "IP", "IQV", "IR", "IRM", "ISRG", "IT", "ITW",
    "IVZ", "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JPM", "KDP", "KEY",
    "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI", "KO", "KR", "L",
    "LDOS", "LEN", "LH", "LHX", "LII", "LIN", "LITE", "LLY", "LMT", "LNT",
    "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV", "MA", "MAA",
    "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET", "META",
    "MGM", "MHK", "MKC", "MLM", "MMM", "MNST", "MO", "MOH", "MOS", "MPC",
    "MPWR", "MRK", "MRNA", "MRVL", "MRSH", "MS", "MSCI", "MSFT", "MSI", "MTB",
    "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX", "NI",
    "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR",
    "NWS", "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC", "ON", "ORCL", "ORLY",
    "OTIS", "OXY", "PANW", "PAYC", "PAYX", "PCAR", "PCG", "PEG", "PEP",
    "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PLTR", "PM",
    "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX",
    "PTC", "PWR", "PYPL", "QCOM", "QRVO", "RCL", "REG", "REGN", "RF", "RJF",
    "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG", "RTX", "RVTY", "SBAC",
    "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA", "SNDK", "SNPS",
    "SO", "SOLV", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ",
    "SWK", "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY", "TECH",
    "TEL", "TER", "TFC", "TGT", "TJX", "TKO", "TMO", "TMUS", "TPR", "TRGP",
    "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT", "TTWO", "TWLO", "TXN",
    "TXT", "TYL", "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS",
    "URI", "USB", "V", "VEEV", "VICI", "VLO", "VLTO", "VMC", "VRSK",
    "VRSN", "VRT", "VRTX", "VST", "VTR", "VTRS", "VZ", "WAB", "WAT",
    "WDAY", "WDC", "WEC", "WELL", "WFC", "WM", "WMB", "WMT", "WRB", "WSM",
    "WST", "WTW", "WY", "WYNN", "XEL", "XOM", "XYL", "XYZ", "YUM", "ZBH",
    "ZBRA", "ZTS"
]

DATA_FILE = "market_data.csv"

def get_last_trading_day():
    today = datetime.utcnow()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")

def bootstrap_history_fast():
    print(f"Bootstrapping historical data for {len(WATCHLIST)} tickers...")
    yf_tickers = [t.replace(".", "-") for t in WATCHLIST]
    
    data = yf.download(yf_tickers, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
    all_rows = []
    
    for orig_ticker, yf_t in zip(WATCHLIST, yf_tickers):
        if yf_t in data.columns.levels:
            sub = data[yf_t].dropna(subset=["Close"])
            for dt, row in sub.iterrows():
                all_rows.append({
                    "Ticker": orig_ticker,
                    "Date": dt.strftime("%Y-%m-%d"),
                    "Open": round(float(row["Open"]), 4),
                    "High": round(float(row["High"]), 4),
                    "Low": round(float(row["Low"]), 4),
                    "Close": round(float(row["Close"]), 4),
                    "Volume": int(row["Volume"])
                })
                
    df = pd.DataFrame(all_rows)
    df.to_csv(DATA_FILE, index=False)
    print(f"Bootstrap completed! Saved {len(df)} rows.")
    return df

def update_daily_grouped(df):
    target_date = get_last_trading_day()
    if target_date in df["Date"].values:
        print(f"Data for {target_date} already exists.")
        return df

    print(f"Fetching Grouped Daily bars from Massive for {target_date}...")
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{target_date}?adjusted=true&apiKey={API_KEY}"
    res = requests.get(url).json()
    
    if "results" not in res:
        print("No new data returned from Massive (holiday or market still open).")
        return df

    watchlist_set = set(WATCHLIST)
    new_rows = []
    for bar in res["results"]:
        ticker = bar.get("T")
        if ticker in watchlist_set:
            new_rows.append({
                "Ticker": ticker,
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
        df = df.sort_values("Date").groupby("Ticker").tail(260).reset_index(drop=True)
        df.to_csv(DATA_FILE, index=False)
        print(f"Updated {len(new_rows)} tickers successfully.")
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
    
    recent = sub_df.tail(55).reset_index(drop=True)
    curr = recent.iloc[-1]
    prev = recent.iloc[-2]
    
    # Pattern 1: Rectangle / Darvas Box (last 37 bars)
    box_df = recent.iloc[-38:-1]
    box_high = box_df["High"].max()
    box_low = box_df["Low"].min()
    box_range_pct = ((box_high - box_low) / box_low) * 100
    
    if box_range_pct <= 15.0 and prev["Close"] <= box_high and curr["Close"] > box_high and curr["Rel_Vol"] >= 1.3:
        send_alert(
            ticker=ticker,
            pattern_he="פריצת מלבן / דרווס בוקס",
            pattern_en="RECTANGLE / DARVAS BOX",
            sub_df=sub_df.tail(120),
            resistance=box_high,
            support=box_low,
            extra_label="Box Range",
            extra_val=f"{box_range_pct:.1f}%   •   37 bars",
            trend_line=None
        )
        return

    # Pattern 2: Descending Trendline (last 55 bars)
    peak_idx = recent["High"].iloc[:-10].idxmax()
    peak_price = recent.loc[peak_idx, "High"]
    peak_date = recent.loc[peak_idx, "Date"]
    
    mid_df = recent.iloc[peak_idx+5:-2]
    if len(mid_df) > 5:
        sec_idx = mid_df["High"].idxmax()
        sec_price = recent.loc[sec_idx, "High"]
        
        slope = (sec_price - peak_price) / (sec_idx - peak_idx)
        if slope < 0:
            curr_idx = len(recent) - 1
            trend_resistance = peak_price + slope * (curr_idx - peak_idx)
            prev_resistance = peak_price + slope * (curr_idx - 1 - peak_idx)
            
            if prev["Close"] <= prev_resistance and curr["Close"] > trend_resistance and curr["Rel_Vol"] >= 1.3:
                drop_pct = ((curr["Close"] - peak_price) / peak_price) * 100
                bars_count = curr_idx - peak_idx
                support_lvl = recent.iloc[peak_idx:]["Low"].min()
                
                send_alert(
                    ticker=ticker,
                    pattern_he="פריצת קו מגמה יורד",
                    pattern_en="DESCENDING TRENDLINE",
                    sub_df=sub_df.tail(120),
                    resistance=trend_resistance,
                    support=support_lvl,
                    extra_label="Trend Drop",
                    extra_val=f"{drop_pct:.1f}%   •   {bars_count} bars",
                    trend_line=[(peak_date, peak_price), (curr["Date"], trend_resistance)]
                )

def generate_chart(ticker, plot_df, resistance, support, trend_line):
    plot_df = plot_df.copy()
    plot_df["Date"] = pd.to_datetime(plot_df["Date"])
    plot_df.set_index("Date", inplace=True)
    
    mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', edge='inherit', wick='inherit', volume={'up': '#26a69a', 'down': '#ef5350'})
    style = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc, facecolor='#0b0e11', figcolor='#0b0e11', gridcolor='#1e222d', gridstyle=':')
    
    alines_list = []
    colors_list = []
    
    start_d = plot_df.index[0].strftime("%Y-%m-%d")
    end_d = plot_df.index[-1].strftime("%Y-%m-%d")
    alines_list.append([(start_d, support), (end_d, support)])
    colors_list.append('#26a69a')
    
    if trend_line:
        alines_list.append(trend_line)
    else:
        alines_list.append([(start_d, resistance), (end_d, resistance)])
    colors_list.append('#ef5350')

    mpf.plot(
        plot_df, type='candle', style=style, volume=True,
        title=f"\n{ticker} Daily",
        alines=dict(alines=alines_list, colors=colors_list, linestyle='--', linewidths=1.2),
        savefig=dict(fname='chart.png', dpi=150, bbox_inches='tight', facecolor='#0b0e11')
    )

def send_alert(ticker, pattern_he, pattern_en, sub_df, resistance, support, extra_label, extra_val, trend_line):
    curr = sub_df.iloc[-1]
    price = curr["Close"]
    pct_above = ((price - resistance) / resistance) * 100
    rel_vol = curr["Rel_Vol"]
    atr = curr["ATR_Pct"]
    vs_200ma = "above ✅" if pd.notna(curr["SMA200"]) and price > curr["SMA200"] else "below ❌"
    
    stop = support
    target = price + (price - stop) * 2.5
    stop_pct = ((stop - price) / price) * 100
    target_pct = ((target - price) / price) * 100
    rr = abs((target - price) / (price - stop)) if price != stop else 0

    generate_chart(ticker, sub_df, resistance, support, trend_line)

    backticks = "```"
    table_text = (
        f"{backticks}\n"
        f"{pattern_en:<25} •   Daily\n"
        f"────────────────────────────────────────\n"
        f"Price          ${price:.2f}\n"
        f"Resistance     {resistance:.2f}   ▲ +{pct_above:.2f}%\n"
        f"Rel Volume     {rel_vol:.2f}x\n"
        f"ATR (Daily)    {atr:.2f}%   🟢\n"
        f"{extra_label:<14} {extra_val}\n"
        f"vs 200MA       {vs_200ma}\n"
        f"Entry          {price:.2f}\n"
        f"Stop           {stop:.2f}   ({stop_pct:.1f}%)\n"
        f"Target         {target:.2f}   (+{target_pct:.1f}%)\n"
        f"R : R          {rr:.2f}\n"
        f"{backticks}"
    )

    payload = {
        "embeds": [
            {
                "title": f"🐍 Daily • {pattern_he} — {ticker}",
                "description": f"**פרץ תבנית {pattern_he} מעל התנגדות {ticker} {resistance:.2f}**\n{table_text}\n[📊 פתח ב-TradingView](https://www.tradingview.com/chart/?symbol={ticker})",
                "color": 3066993,
                "image": {"url": "attachment://chart.png"},
                "footer": {"text": f"Massive API Scanner • {curr['Date']} IL"}
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
        df = pd.read_csv(DATA_FILE)
        df = update_daily_grouped(df)

    for ticker in WATCHLIST:
        sub = df[df["Ticker"] == ticker]
        if not sub.empty:
            sub = calculate_indicators(sub)
            check_patterns_and_alert(ticker, sub)
