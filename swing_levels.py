#!/usr/bin/env python3
"""Swing High & Lows Bot - stocks sitting on a swing level -> Discord webhook.

For each timeframe (Daily / Weekly / Monthly) the script finds the most recent
confirmed swing high and swing low (a pivot with SWING_BARS lower/higher bars on
each side). A stock matches when its price is within +/-PROXIMITY_PCT of one of
those levels. Stocks matching on 2+ timeframes are listed as Confluence.

pip install yfinance pandas requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python swing_levels.py
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python swing_levels.py
The first run also fetches each stock's sector (a minute or two) and saves it
to sectors_cache.json next to the script (shared with sniper_sma.py).
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
WEBHOOK_URL = "https://discord.com/api/webhooks/1570178540274450585/KRPPrqWt3SVzOWEaI9--K6KoYChF00EWg_JZkNk7STUjqzSa-e9rh-hSQCQBVo8kYKpy"
BOT_NAME = "Swing High & Lows Bot"
PROXIMITY_PCT = 0.5                                         # price within +/-0.5% of the level
SWING_BARS = {"Daily": 3, "Weekly": 3, "Monthly": 2}        # bars on each side of a pivot
RESAMPLE = {"Daily": None, "Weekly": "W-FRI", "Monthly": "MS"}
MIN_SAME_SIGNAL = 2    # sector read-out needs this many stocks with the same signal
MIN_SECTOR_SIZE = 5    # ...and this many stocks in the sector to judge its trend
TREND_UP_PCT, TREND_DOWN_PCT = 60, 40   # % of sector above its SMA200 -> up / down
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sectors_cache.json")
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

SECTOR_HE = {
    "Basic Materials": "חומרים", "Communication Services": "טלקומוניקציה",
    "Consumer Cyclical": "צריכה מחזורית", "Consumer Defensive": "צריכה בסיסית",
    "Energy": "אנרגיה", "Financial Services": "שירותים פיננסים", "Healthcare": "בריאות",
    "Industrials": "תעשייה", "Real Estate": 'נדל"ן', "Technology": "טכנולוגיה",
    "Utilities": "תשתיות", "Unknown": "לא ידוע",
}
TF_HE = {"Daily": "יומית", "Weekly": "שבועית", "Monthly": "חודשית"}

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


# ---- swing levels -----------------------------------------------------------
def last_swings(highs, lows, n):
    """Most recent confirmed swing high / swing low prices (None if not found)."""
    sh = sl = None
    for i in range(len(highs) - n - 1, n - 1, -1):   # newest confirmed pivot first
        if sh is None and highs[i] > highs[i - n:i].max() and highs[i] >= highs[i + 1:i + n + 1].max():
            sh = float(highs[i])
        if sl is None and lows[i] < lows[i - n:i].min() and lows[i] <= lows[i + 1:i + n + 1].min():
            sl = float(lows[i])
        if sh is not None and sl is not None:
            break
    return sh, sl


def scan():
    data = download(TICKERS, "1d", "5y")
    hits = {tf: {"High": [], "Low": []} for tf in SWING_BARS}
    tfs_of, events, uptrend, scanned = {}, [], {}, 0   # events = (ticker, timeframe, side)

    for t in TICKERS:
        df = get(data, yahoo(t))
        if df is None or len(df) < 30:
            continue
        scanned += 1
        price = float(df.Close.iloc[-1])
        if len(df) >= 200:
            uptrend[t] = price > float(df.Close.iloc[-200:].mean())

        for tf, rule in RESAMPLE.items():
            bars = df if rule is None else df.resample(rule).agg(
                {"High": "max", "Low": "min", "Close": "last"}).dropna()
            sh, sl = last_swings(bars.High.values, bars.Low.values, SWING_BARS[tf])
            for side, level in (("High", sh), ("Low", sl)):
                if level is not None and abs(price / level - 1) * 100 <= PROXIMITY_PCT:
                    hits[tf][side].append(t)
                    tfs_of.setdefault(t, set()).add(tf)
                    events.append((t, tf, side))

    for h in hits.values():
        for ts in h.values():
            ts.sort()
    return hits, tfs_of, events, uptrend, scanned


def remark(side, up):
    """Rule-based market remark from the sector's trend (up = % of sector above SMA200)."""
    if up is None:
        return ""
    if side == "Low" and up >= TREND_UP_PCT:
        return "חיזוק מגמת עלייה בשוק"
    if side == "High" and up <= TREND_DOWN_PCT:
        return "חיזוק מגמת ירידה בשוק"
    return "חוסר יציבות בשוק"


def sector_analysis(events, uptrend, sectors):
    """Signals grouped by sector: same level type + timeframe on 2+ stocks."""
    by_sector = {}
    for t, tf, side in events:
        by_sector.setdefault(sectors.get(t, "Unknown"), {}).setdefault((side, tf), set()).add(t)

    lines = []
    for sec in sorted(by_sector, key=lambda s: -sum(len(v) for v in by_sector[s].values())):
        name = SECTOR_HE.get(sec, sec)
        members = [t for t in uptrend if sectors.get(t) == sec]
        up = None
        if sec != "Unknown" and len(members) >= MIN_SECTOR_SIZE:
            up = sum(uptrend[t] for t in members) / len(members) * 100

        groups = [(k, v) for k, v in by_sector[sec].items() if len(v) >= MIN_SAME_SIGNAL]
        if not groups:
            lines.append(f"• {name} — אין מספיק מניות באותו סיגנל.")
            continue
        for (side, tf), ts in sorted(groups, key=lambda kv: -len(kv[1])):
            kind = "תמיכה" if side == "Low" else "התנגדות"   # swing low = support, high = resistance
            tail = f", {remark(side, up)}" if remark(side, up) else ""
            lines.append(f"• {name} — {', '.join(sorted(ts))}: תבנית {kind} {TF_HE[tf]}{tail}.")
    return lines[:12]


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


def send_list(head, ts):
    for i, part in enumerate(chunks(ts)):
        post({"content": f"{head if i == 0 else ''}```{','.join(part)}```"})


def main():
    hits, tfs_of, events, uptrend, scanned = scan()
    now = dt.datetime.now(TZ)
    conf = {n: sorted(t for t, s in tfs_of.items() if len(s) == n) for n in (3, 2)}
    n_conf = sum(len(v) for v in conf.values())

    if events:  # sector read-out first, like the original channel layout
        lines = sector_analysis(events, uptrend, load_sectors(TICKERS))
        if lines:
            post({"embeds": [{
                "title": "🤖 ניתוח סקטוריאלי",
                "description": "\n\n".join(lines)[:4000],
                "color": 0x9B59B6,
                "footer": {"text": "Strat Ninja • Swing Levels"},
            }]})

    tf_lines = [f"**{tf}:** {len(h['High']) + len(h['Low'])} "
                f"(▲High: {len(h['High'])} | ▼Low: {len(h['Low'])})" for tf, h in hits.items()]
    post({"embeds": [{
        "title": "🎯 Swing Level Scanner",
        "description": (f"📅 {now:%d-%m-%Y %H:%M}\n"
                        f"📊 סורקו: {scanned} | התאמות: **{len(events)}**\n"
                        f"🎯 קרבה: ±{PROXIMITY_PCT:g}%\n"
                        f"🔥 Confluence (2+ TF): **{n_conf}**\n\n" + "\n".join(tf_lines)),
        "color": 0xE8A33D,
        "footer": {"text": "Strat Ninja • Swing Levels"},
    }]})

    for n in (3, 2):
        if conf[n]:
            send_list(f"🔥 **Confluence — {n} Timeframes** · {len(conf[n])}\n", conf[n])
    for tf, h in hits.items():
        for side, sym in (("High", "▲"), ("Low", "▼")):
            if h[side]:
                send_list(f"{sym} **Swing {side} — {tf}** · {len(h[side])}\n", h[side])


if __name__ == "__main__":
    main()
