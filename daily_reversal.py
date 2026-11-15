#!/usr/bin/env python3
"""Strat Daily Reversal (COMPLETED) -> Discord webhook.

Finds stocks that took out yesterday's LOW first (a 2D), reversed, and then also
took out yesterday's HIGH, so the reversal has reached the outside bar (3).
Works during the session (candle still open) or after the close (candle final).

pip install yfinance pandas requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python daily_reversal.py
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python daily_reversal.py
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
WEBHOOK_URL = "https://discord.com/api/webhooks/1570177602956697650/AM1fTJP8LAtmdr9fMeHpEfr0l3DU_kZKgcFbhdkA-f9c62xB0DBEv2sS6fR1bFmM981_"
BOT_NAME = "DAILY_REVERSAL"
MIN_PRICE, MAX_PRICE = 2, 1000
REQUIRE_LOW_FIRST = True  # the day's low must come before its high (a true 2D reversal)
MAX_ROWS = 25             # rows shown in the embed (the copy-paste list has all of them)
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

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


def rsi14(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return float((100 - 100 / (1 + up / dn)).iloc[-1])


# ---- scan -------------------------------------------------------------------
def scan():
    daily = download(TICKERS, "1d", "1y")
    cands, scanned = [], 0

    # step 1 (daily bars): today took out BOTH yesterday's low and yesterday's high
    for t in TICKERS:
        df = get(daily, yahoo(t))
        if df is None or len(df) < 30:
            continue
        scanned += 1
        cur, prev = df.iloc[-1], df.iloc[-2]
        if not (MIN_PRICE <= cur.Close <= MAX_PRICE):
            continue
        if cur.Low < prev.Low and cur.High > prev.High:
            cands.append({
                "t": t,
                "price": float(cur.Close),
                "pct": float((cur.Close / prev.High - 1) * 100),  # vs yesterday's high
                "rsi": rsi14(df.Close),
                "final": False,      # True once the 15:45 bar exists (candle closed)
                "low_first": None,   # None = unknown (no intraday data)
            })

    # step 2 (15-minute bars, candidates only): was the low set BEFORE the high?
    if cands:
        intra = download([c["t"] for c in cands], "15m", "5d")
        for c in cands:
            idf = get(intra, yahoo(c["t"]))
            if idf is None or idf.empty:
                continue
            c["final"] = bool(idf.index[-1].time() >= dt.time(15, 45))
            day = idf[idf.index.date == idf.index[-1].date()]
            c["low_first"] = bool(day.Low.idxmin() < day.High.idxmax())

    if REQUIRE_LOW_FIRST:  # unknown (None) is kept, only a confirmed "high first" is dropped
        cands = [c for c in cands if c["low_first"] is not False]
    cands.sort(key=lambda c: c["pct"], reverse=True)
    return cands, scanned


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


def dot(c):
    if c["pct"] < 0:
        return "🟡"                       # broke the high, but is back below it
    return "🔒" if c["final"] else "🟢"   # 🔒 closed above, 🟢 above right now


def main():
    rows, scanned = scan()
    n = len(rows)
    now = dt.datetime.now(TZ)

    desc = (
        f"📅 {now:%d-%m-%Y %H:%M}\n\n"
        "**Strat Daily Reversal — הושלם (נר 3)** ✅\n"
        "מניות שהיו 2D reversal (שברו את שפל אתמול וחזרו) ופרצו גם את הגבוה של אתמול — "
        "ההיפוך הגיע לנר 3 (שיא חדש).\n"
        "🔒 = גם סגר מעל הגבוה · 🟢 = מעל הגבוה כרגע · 🟡 = חזר מתחת\n"
        f"Scanned: {scanned} | ✅ הושלם: {n}"
    )

    if n:
        w = max(len(c["t"]) for c in rows)
        lines = []
        for c in rows[:MAX_ROWS]:
            where = "מעל הגבוה" if c["pct"] >= 0 else "מתחת לגבוה"
            lines.append(f"`{c['t']:<{w}}` {dot(c)} ${c['price']:,.2f} | "
                         f"{c['pct']:+.1f}% {where} | RSI {c['rsi']:.0f}")
        if n > MAX_ROWS:
            lines.append(f"… +{n - MAX_ROWS}")
        paste = ", ".join(c["t"] for c in rows[:150])
        desc += (f"\n\n✅ **הושלם | {n}**\n" + "\n".join(lines)
                 + f"\n\n📋 **Tickers (copy-paste)**\n```{paste}```")
    else:
        desc += "\n\nאין כרגע מניות שהשלימו היפוך."

    post({"embeds": [{
        "title": "✅ Strat Daily Reversal — COMPLETED (נר 3)",
        "description": desc,
        "color": 0x52B788,
        "footer": {"text": "Strat Ninja • Daily REV completion"},
    }]})


if __name__ == "__main__":
    main()
