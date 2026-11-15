#!/usr/bin/env python3
"""All-Time / 52-Week highs & lows -> Discord webhook.

A stock is listed when TODAY's daily candle made a new high / low:
  ATH  - High above every previous high in the stock's whole history
  ATL  - Low below every previous low
  52WH - High above the highest high of the previous 52 weeks
  52WL - Low below the lowest low of the previous 52 weeks
Each stock appears once, in its strongest group (ATH > ATL > 52WH > 52WL).
Inside a group the biggest breakout / breakdown comes first.

pip install yfinance pandas requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python highs_lows.py   (run after the US close; it downloads full history, so allow a few minutes)
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python highs_lows.py
"""
import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ---- settings ---------------------------------------------------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1571317719440302082/nbSs_G9PGi2yR4fNGOFFgWYtMJ3-GSa2GLoF4JkYXHw9e6Q2iHzBvd42hQtJXuCyB6_A"
BOT_NAME = "StratNinja_Highs_Lows"
MIN_BARS = 30          # ignore stocks with less history than this
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

GROUPS = [  # (key, emoji, hebrew description) - in the order they are posted
    ("ATH", "🚀", "שיא כל הזמנים (לונג חזק)"),
    ("52WH", "🟢", "שיא 52 שבועות"),
    ("ATL", "💀", "שפל כל הזמנים (חולשה קיצונית)"),
    ("52WL", "🔴", "שפל 52 שבועות"),
]

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


# ---- data -------------------------------------------------------------------
def yahoo(t):
    """Yahoo writes class shares with a dash (BRK-B); TradingView with a dot (BRK.B)."""
    return t.replace(".", "-")


def get(data, sym):
    """One ticker's OHLCV table, or None if Yahoo returned nothing for it."""
    try:
        return data[sym].dropna()
    except KeyError:
        return None


# ---- scan -------------------------------------------------------------------
def classify(df):
    """(group, breakout %) for the last bar, or None."""
    prev = df.iloc[:-1]
    if len(prev) < MIN_BARS:
        return None
    cur = df.iloc[-1]
    year = prev[prev.index > df.index[-1] - pd.Timedelta(days=365)]

    # strongest group first
    if cur.High > prev.High.max():
        return "ATH", (cur.High / prev.High.max() - 1) * 100
    if cur.Low < prev.Low.min():
        return "ATL", (1 - cur.Low / prev.Low.min()) * 100
    if cur.High > year.High.max():
        return "52WH", (cur.High / year.High.max() - 1) * 100
    if cur.Low < year.Low.min():
        return "52WL", (1 - cur.Low / year.Low.min()) * 100
    return None


def scan(chunk=100):
    """Downloads full history in chunks (keeps memory low) and sorts every stock into one group."""
    found = {key: [] for key, _, _ in GROUPS}   # key -> [(breakout %, ticker)]
    scanned = 0
    for i in range(0, len(TICKERS), chunk):
        part = TICKERS[i:i + chunk]
        syms = [yahoo(t) for t in part]
        if len(syms) == 1:
            syms.append("SPY")  # keeps the multi-ticker column layout
        print(f"Downloading {min(i + chunk, len(TICKERS))}/{len(TICKERS)} ...")
        try:
            data = yf.download(syms, period="max", interval="1d", group_by="ticker",
                               auto_adjust=False, progress=False, threads=True)
        except Exception as e:
            print(f"  chunk failed ({e}); skipping it")
            continue
        for t in part:
            df = get(data, yahoo(t))
            if df is None or len(df) < MIN_BARS + 1:
                continue
            scanned += 1
            hit = classify(df)
            if hit:
                found[hit[0]].append((hit[1], t))

    for key, items in found.items():
        items.sort(reverse=True)                          # biggest breakout first
        found[key] = [t for _, t in items]
    return found, scanned


# ---- Discord ----------------------------------------------------------------
def post(payload):
    payload["username"] = BOT_NAME
    if os.environ.get("DRY_RUN"):
        try:
            print(json.dumps(payload, ensure_ascii=False, indent=1))
        except UnicodeEncodeError:
            print(json.dumps(payload, ensure_ascii=True, indent=1))
        return
    if "PASTE_YOUR" in WEBHOOK_URL:
        raise SystemExit("Paste your webhook URL into WEBHOOK_URL at the top of the file.")
    while True:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code == 429:  # rate limited
            time.sleep(r.json().get("retry_after", 1))
            continue
        r.raise_for_status()
        return


def rows(tickers, per_row=10):
    """Ten tickers per line so Discord never splits a ticker across two lines."""
    return ",\n".join(",".join(tickers[i:i + per_row]) for i in range(0, len(tickers), per_row))


def main():
    found, scanned = scan()
    print(f"Scanned {scanned} stocks")
    now = dt.datetime.now(TZ)
    n = {key: len(v) for key, v in found.items()}

    post({"embeds": [{
        "title": "🏔️ All-Time / 52-Week — שיאים ושפלים",
        "description": (f"📅 {now:%d-%m-%Y %H:%M}\n"
                        "מניות מהיקום שעשו **שיא/שפל חדש היום** (לפי ה-High/Low של הנר היומי).\n"
                        "כל מניה מופיעה פעם אחת — בקבוצה החזקה ביותר שלה.\n\n"
                        f"🚀 ATH **{n['ATH']}** · 💀 ATL **{n['ATL']}** | "
                        f"🟢 52WH **{n['52WH']}** · 🔴 52WL **{n['52WL']}**"),
        "color": 0xF1C40F,
        "footer": {"text": "Strat Ninja • ATH/ATL/52W"},
    }]})

    for key, emoji, note in GROUPS:
        ts = found[key]
        for i in range(0, len(ts), 150):                  # stay under Discord's 2000-char limit
            head = f"{emoji} **{key}** · {len(ts)} · {note}\n" if i == 0 else ""
            post({"content": f"{head}```{rows(ts[i:i + 150])}```"})


if __name__ == "__main__":
    main()
