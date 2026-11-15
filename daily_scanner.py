#!/usr/bin/env python3
"""Daily Combo Scanner -> Discord webhook (Strat patterns).

pip install yfinance pandas requests tzdata
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python daily_scanner.py
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python daily_scanner.py
"""
import json
import os
import time
import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ---- settings ---------------------------------------------------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1570179340895920138/wKW_p48lw-OwCom5MF3eftxCZ8r37i-av5VuSUYRmmuS5iPQCwEYQCGCWMKDqFIBQ0K7" 

TICKERS = [
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
    "DVN", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EG", "EIX", "EL",
    "ELV", "EME", "EMR", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ERIE", "ES",
    "ESS", "ETN", "ETR", "EVRG", "EW", "EXC", "EXE", "EXPD", "EXPE", "EXR",
    "F", "FANG", "FAST", "FCX", "FDS", "FDX", "FE", "FERG", "FFIV", "FICO",
    "FIS", "FISV", "FITB", "FLEX", "FIX", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD", "GIS", "GL",
    "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HIG", "HII", "HLT", "HOLX", "HON",
    "HOOD", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB", "HUM", "HWM",
    "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC", "INTU", "INVH",
    "IP", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ", "J", "JBHT",
    "JBL", "JCI", "JKHY", "JNJ", "JPM", "KDP", "KEY", "KEYS", "KHC", "KIM",
    "KKR", "KLAC", "KMB", "KMI", "KO", "KR", "L", "LDOS", "LEN", "LH",
    "LHX", "LII", "LIN", "LITE", "LLY", "LMT", "LNT", "LOW", "LRCX", "LULU",
    "LUV", "LVS", "LW", "LYB", "LYV", "MA", "MAA", "MAR", "MAS", "MCD",
    "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET", "META", "MGM", "MHK", "MKC",
    "MLM", "MMM", "MNST", "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA",
    "MRVL", "MRSH", "MS", "MSCI", "MSFT", "MSI", "MTB", "MTCH", "MTD", "MU",
    "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX", "NI", "NKE", "NOC", "NOW",
    "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWS", "NWSA", "NXPI",
    "O", "ODFL", "OKE", "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY", "PANW",
    "PAYC", "PAYX", "PCAR", "PCG", "PEG", "PEP", "PFE", "PFG", "PG", "PGR",
    "PH", "PHM", "PKG", "PLD", "PLTR", "PM", "PNC", "PNR", "PNW", "PODD",
    "POOL", "PPG", "PPL", "PRU", "PSA", "PSX", "PTC", "PWR", "PYPL", "QCOM",
    "QRVO", "RCL", "REG", "REGN", "RF", "RJF", "RL", "RMD", "ROK", "ROL",
    "ROP", "ROST", "RSG", "RTX", "RVTY", "SBAC", "SBUX", "SCHW", "SHW", "SJM",
    "SLB", "SMCI", "SNA", "SNDK", "SNPS", "SO", "SOLV", "SPG", "SPGI", "SRE",
    "STE", "STLD", "STT", "STX", "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY",
    "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TGT", "TJX",
    "TKO", "TMO", "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSLA",
    "TSN", "TT", "TTWO", "TWLO", "TXN", "TXT", "TYL", "UAL", "UBER", "UDR",
    "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB", "V", "VEEV", "VICI",
    "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRT", "VRTX", "VST", "VTR", "VTRS",
    "VZ", "WAB", "WAT", "WDAY", "WDC", "WEC", "WELL", "WFC", "WM", "WMB",
    "WMT", "WRB", "WSM", "WST", "WTW", "WY", "WYNN", "XEL", "XOM", "XYL",
    "XYZ", "YUM", "ZBH", "ZBRA", "ZTS",
]

MIN_PRICE, MAX_PRICE = 2, 1000
VOL_MULT = 1.2      # volume >= 1.2 x average of the previous 20 days
WICK_RATIO = 0.6    # wick >= 60% of the candle range -> Hammer / Shooting Star
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

BULL = ["2D In-Conflict", "Hammer"]
BEAR = ["2U In-Conflict", "Shooting Star"]
OUTSIDE = ["Outside Green", "Outside Red"]


# ---- Strat logic ------------------------------------------------------------
def strat_type(cur, prev):
    """'1' inside, '2U' / '2D' directional, '3' outside."""
    if cur.High > prev.High and cur.Low < prev.Low:
        return "3"
    if cur.High <= prev.High and cur.Low >= prev.Low:
        return "1"
    return "2U" if cur.High > prev.High else "2D"


def color(c):
    """+1 green candle, -1 red candle, 0 doji."""
    return 1 if c.Close > c.Open else -1 if c.Close < c.Open else 0


def wick_pattern(c):
    rng = c.High - c.Low
    if rng <= 0:
        return None
    lower = (min(c.Open, c.Close) - c.Low) / rng
    upper = (c.High - max(c.Open, c.Close)) / rng
    if lower >= WICK_RATIO:
        return "Hammer"
    if upper >= WICK_RATIO:
        return "Shooting Star"
    return None


def ftfc(df):
    """+1 if the current Day, Week and Month candles are all green, -1 if all red, else 0."""
    agg = {"Open": "first", "Close": "last"}
    d = df.iloc[-1]
    w = df.resample("W-FRI").agg(agg).iloc[-1]
    m = df.resample("MS").agg(agg).iloc[-1]
    colors = {color(d), color(w), color(m)}
    return colors.pop() if len(colors) == 1 else 0


# ---- scan -------------------------------------------------------------------
def download(tickers, chunk=100):
    """Downloads in chunks so Yahoo doesn't throttle a 500-ticker request.
    Yahoo writes class shares with a dash (BRK-B), TradingView with a dot (BRK.B)."""
    frames = []
    for i in range(0, len(tickers), chunk):
        part = [t.replace(".", "-") for t in tickers[i:i + chunk]]
        frames.append(yf.download(part, period="2y", interval="1d", group_by="ticker",
                                  auto_adjust=False, progress=False, threads=True))
    return pd.concat(frames, axis=1)


def scan(tickers):
    data = download(tickers)
    res = {k: [] for k in BULL + BEAR + OUTSIDE}
    scanned = ftfc_up = ftfc_down = 0

    for t in tickers:
        try:
            df = data[t.replace(".", "-")].dropna()
        except KeyError:
            continue
        if len(df) < 25:
            continue
        scanned += 1

        cur, prev = df.iloc[-1], df.iloc[-2]
        avg_vol = df.Volume.iloc[-21:-1].mean()
        if not (MIN_PRICE <= cur.Close <= MAX_PRICE) or cur.Volume < VOL_MULT * avg_vol:
            continue

        kind, col, wp = strat_type(cur, prev), color(cur), wick_pattern(cur)
        if kind == "2D" and col > 0:
            res["2D In-Conflict"].append(t)      # 2D bar that closed green
        if kind == "2U" and col < 0:
            res["2U In-Conflict"].append(t)      # 2U bar that closed red
        if kind == "3" and col > 0:
            res["Outside Green"].append(t)
        if kind == "3" and col < 0:
            res["Outside Red"].append(t)
        if wp:
            res[wp].append(t)

        f = ftfc(df)
        ftfc_up += f > 0
        ftfc_down += f < 0

    return res, scanned, ftfc_up + ftfc_down


# ---- Discord ----------------------------------------------------------------
def post(payload):
    payload["username"] = "Daily Scanner"
    if os.environ.get("DRY_RUN"):
        print(json.dumps(payload, ensure_ascii=True, indent=1))
        return
    url = WEBHOOK_URL
    while True:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 429:  # rate limited
            time.sleep(r.json().get("retry_after", 1))
            continue
        r.raise_for_status()
        return


def block(emoji, title, names, res, per_msg=250):
    """Returns a list of messages (split so each stays under Discord's 2000-char limit)."""
    uniq = sorted({t for n in names for t in res[n]})
    parts = " · ".join(f"{n} (All) {len(res[n])}" for n in names if res[n])
    msgs = []
    for i in range(0, len(uniq), per_msg):
        head = f"{emoji} **{title} ({len(uniq)})** · {parts}\n" if i == 0 else ""
        # comma-separated, no spaces: pastes straight into a TradingView watchlist
        msgs.append(f"{head}```{','.join(uniq[i:i + per_msg])}```")
    return msgs


def main():
    res, scanned, aligned = scan(TICKERS)
    bull = {t for n in BULL for t in res[n]}
    bear = {t for n in BEAR for t in res[n]}
    out = {t for n in OUTSIDE for t in res[n]}
    now = dt.datetime.now(TZ)

    embed = {
        "title": "📊 Daily Combo Scanner",
        "description": (
            f"📅 {now:%d-%m-%Y} ⏰ {now:%H:%M}\n\n"
            f"📊 **Scan Summary:**\n"
            f"Scanned: {scanned} | Unique signals: {len(bull | bear | out)}\n"
            f"🟢 BULL: {len(bull)} 🔴 BEAR: {len(bear)}\n\n"
            f"FTFC D/W/M aligned: {aligned}"
        ),
        "color": 0x4A7BD0,
        "footer": {"text": "Strat Ninja • Daily Combo"},
    }
    post({"embeds": [embed]})

    for text in (block("🟢", "BULL Daily", BULL, res)
                 + block("🔴", "BEAR Daily", BEAR, res)
                 + block("⚡", "Outside", OUTSIDE, res)):
        post({"content": text})


if __name__ == "__main__":
    main()
