#!/usr/bin/env python3
"""SniperSMA - SMA 50/100/150/200 compression -> Discord webhook.

A stock is "compressed" when its four moving averages (50/100/150/200, daily)
all sit within MAX_SPREAD_PCT of each other. Then, by where the price is:
  INSIDE = price inside the cluster
  BULL   = price above the cluster (cluster = multiple support)
  BEAR   = price below the cluster (cluster = multiple resistance)

pip install yfinance pandas requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python sniper_sma.py
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python sniper_sma.py
The first run also fetches each stock's sector (a minute or two) and saves it
to sectors_cache.json next to the script, so later runs are fast.
"""
import datetime as dt
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ---- settings ---------------------------------------------------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1570178157703598090/mgw5DenTeirkt7exZwc-7QqjJ_BuO8MWXxmaWXnn_0NjirpLCHE86X7rsCrg3wwY9NOT"
BOT_NAME = "SniperSMA"
SMA_LENGTHS = (50, 100, 150, 200)
MAX_SPREAD_PCT = 2.0   # (highest SMA - lowest SMA) / lowest SMA, in % (<=)
BREADTH_PCT = 70       # report a sector when >= 70% of its stocks trend the same way
MIN_SECTOR_SIZE = 5    # ...and only if the sector has at least this many stocks
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sectors_cache.json")
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

SECTOR_HE = {
    "Basic Materials": "חומרים", "Communication Services": "טלקומוניקציה",
    "Consumer Cyclical": "צריכה מחזורית", "Consumer Defensive": "צריכה בסיסית",
    "Energy": "אנרגיה", "Financial Services": "פיננסים", "Healthcare": "בריאות",
    "Industrials": "תעשייה", "Real Estate": 'נדל"ן', "Technology": "טכנולוגיה",
    "Utilities": "תשתיות", "Unknown": "לא ידוע",
}
# kind -> (where the price is relative to the SMA zone, market-direction remark)
VERDICT = {
    "BULL": ("מעל ", "תנועה חיובית בשוק"),
    "BEAR": ("מתחת ל", "תנועה שלילית בשוק"),
    "INSIDE": ("בתוך ", "ממתין לפריצה"),
}
SECTIONS = [
    ("INSIDE", "🎯", "מחיר בתוך הקלאסטר"),
    ("BULL", "📈", "קלאסטר = תמיכה מרובה"),
    ("BEAR", "📉", "קלאסטר = התנגדות מרובה"),
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


def download(tickers, interval, period, chunk=100):
    """Downloads in chunks so Yahoo doesn't throttle one huge request."""
    frames = []
    for i in range(0, len(tickers), chunk):
        part = [yahoo(t) for t in tickers[i:i + chunk]]
        if len(part) == 1:
            part.append("SPY")  # keeps the multi-ticker column layout
        frames.append(yf.download(part, period=period, interval=interval, group_by="ticker",
                                  auto_adjust=False, progress=False, threads=True))
    return pd.concat(frames, axis=1)


def get(data, sym):
    """One ticker's OHLCV table, or None if Yahoo returned nothing for it."""
    try:
        return data[sym].dropna()
    except KeyError:
        return None


def load_sectors(tickers):
    """Sector per ticker from Yahoo, cached in sectors_cache.json."""
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    missing = [t for t in tickers if t not in cache]
    if missing:
        print(f"Fetching sectors for {len(missing)} stocks (first run only)...")

        def fetch(t):
            try:
                return t, yf.Ticker(yahoo(t)).info.get("sector")
            except Exception:
                return t, None

        with ThreadPoolExecutor(max_workers=5) as ex:
            for t, sector in ex.map(fetch, missing):
                if sector:  # failed lookups are retried on the next run
                    cache[t] = sector
        try:
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except Exception:
            pass
    return cache


# ---- scan -------------------------------------------------------------------
def scan():
    data = download(TICKERS, "1d", "2y")
    found = {"INSIDE": [], "BULL": [], "BEAR": []}
    uptrend, scanned = {}, 0   # uptrend[t] = price above its SMA200

    for t in TICKERS:
        df = get(data, yahoo(t))
        if df is None or len(df) < max(SMA_LENGTHS):
            continue
        scanned += 1
        close = df.Close
        smas = [float(close.iloc[-n:].mean()) for n in SMA_LENGTHS]
        price = float(close.iloc[-1])
        uptrend[t] = price > smas[-1]

        lo, hi = min(smas), max(smas)
        if (hi - lo) / lo * 100 > MAX_SPREAD_PCT:
            continue
        if price > hi:
            found["BULL"].append(t)
        elif price < lo:
            found["BEAR"].append(t)
        else:
            found["INSIDE"].append(t)

    for ts in found.values():
        ts.sort()
    return found, uptrend, scanned


def sector_analysis(found, uptrend, sectors):
    """Rule-based sector read-out: signals grouped by sector + sector breadth."""
    by_sector = {}
    for kind, ts in found.items():
        for t in ts:
            by_sector.setdefault(sectors.get(t, "Unknown"), {}).setdefault(kind, []).append(t)

    lines = []
    order = sorted(by_sector, key=lambda s: -sum(len(v) for v in by_sector[s].values()))
    for sec in order:
        name = SECTOR_HE.get(sec, sec)
        for kind in ("BULL", "BEAR", "INSIDE"):
            ts = by_sector[sec].get(kind)
            if ts:
                pos, remark = VERDICT[kind]
                noun = "מחירים" if len(ts) > 1 else "מחיר"
                lines.append(f"• {name} — {', '.join(ts)}: {noun} {pos}אזור ה-SMA, {remark}.")
        members = [t for t in uptrend if sectors.get(t) == sec]
        if sec != "Unknown" and len(members) >= MIN_SECTOR_SIZE:
            up = sum(uptrend[t] for t in members) / len(members) * 100
            if 100 - up >= BREADTH_PCT:
                lines.append(f"• {100 - up:.0f}% מהתעשייה {name} נמצאת במגמת ירידה.")
            elif up >= BREADTH_PCT:
                lines.append(f"• {up:.0f}% מהתעשייה {name} נמצאת במגמת עלייה.")
    return lines


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


def chunks(items, n=250):  # keeps each message under Discord's 2000-char limit
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main():
    found, uptrend, scanned = scan()
    total = sum(len(v) for v in found.values())
    now = dt.datetime.now(TZ)

    desc = (f"📅 {now:%d-%m-%Y %H:%M}\n\n"
            f"**{scanned}** מניות נסרקו · **{total}** בכיווץ ≤ {MAX_SPREAD_PCT:.1f}%\n"
            f"כל 4 הממוצעים (50/100/150/200) בטווח {MAX_SPREAD_PCT:.1f}% — תמיכה/התנגדות מרובה.")
    if not total:
        desc += "\n\nאין כרגע מניות בכיווץ."
    post({"embeds": [{
        "title": "🗜️ SMA Compression — 50 / 100 / 150 / 200",
        "description": desc,
        "color": 0xF1C40F,
        "footer": {"text": "Strat Ninja • SMA Compression"},
    }]})
    if not total:
        return

    for kind, emoji, note in SECTIONS:
        ts = found[kind]
        for i, part in enumerate(chunks(ts)):
            head = f"{emoji} **{kind}** — {len(ts)} · {note}\n" if i == 0 else ""
            post({"content": f"{head}```{','.join(part)}```"})

    lines = sector_analysis(found, uptrend, load_sectors(TICKERS))
    if lines:
        post({"embeds": [{
            "title": "🤖 ניתוח סקטוריאלי",
            "description": "\n\n".join(lines)[:4000],
            "color": 0xF1C40F,
            "footer": {"text": "Strat Ninja • SMA Compression"},
        }]})


if __name__ == "__main__":
    main()
