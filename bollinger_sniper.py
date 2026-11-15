#!/usr/bin/env python3
"""StratNinja_BollingerBands - Bollinger Band reversion scan -> Discord webhook.

Bands: BB(20, 2) on Daily and Weekly bars (two separate blocks, Daily first).
Target of every signal: rebound to the SMA20.
  LONG  = price pierced the LOWER band      SHORT = price pierced the UPPER band
Strength tiers (each stock lands in exactly one):
  Watch         - the candle touched the band but closed back inside (touch only)
  Fire          - the candle CLOSED outside the band
  Squeeze+Fire  - a Fire that came out of a squeeze (band width in its lowest
                  SQUEEZE_PCTL % of the last SQUEEZE_WINDOW bars within the last SQUEEZE_BARS bars)

pip install yfinance pandas numpy requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python bollinger_sniper.py
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python bollinger_sniper.py
"""
import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ---- settings ---------------------------------------------------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1570179044157296770/_IwN3ti23X9U0TpqRcewaYATw8y4kYxoWIJyv3tPlgivDFf5zlXsTtKxmkPfNPamIHwl"
BOT_NAME = "StratNinja_BollingerBands"
TIMEFRAMES = ["Daily", "Weekly"]        # sent one after the other, in this order
RESAMPLE = {"Daily": None, "Weekly": "W-FRI"}
TF_ICON = {"Daily": "📅", "Weekly": "🗓️"}
BB_LEN, BB_MULT = 20, 2
SQUEEZE_WINDOW = {"Daily": 126, "Weekly": 52}   # ~6 months of daily / ~1 year of weekly bars
SQUEEZE_BARS = 5                        # squeeze counts if it happened within the last 5 bars
SQUEEZE_PCTL = 20
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

TIERS = [  # (tier, emoji, heading)
    ("Squeeze+Fire", "💎", "BB Squeeze+Fire"),
    ("Fire", "🔥", "Fire"),
    ("Watch", "👀", "Watch"),
]
SIDES = {  # side -> (dot, embed colour, hebrew explanation)
    "LONG": ("🟢", 0x57F287, "📈 **לונג** = מחיר מתחת BB תחתון → Target: ריבאונד SMA20"),
    "SHORT": ("🔴", 0xED4245, "📉 **שורט** = מחיר מעל BB עליון → Target: ריבאונד SMA20"),
}

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


# ---- signal -----------------------------------------------------------------
def classify(bars, window):
    """(side, tier, %B) for the last bar, or None. %B: 0 = lower band, 1 = upper band."""
    close = bars.Close
    sma = close.rolling(BB_LEN).mean()
    sd = close.rolling(BB_LEN).std(ddof=0)       # population std, like TradingView
    upper, lower = sma + BB_MULT * sd, sma - BB_MULT * sd
    c, h, l = float(close.iloc[-1]), float(bars.High.iloc[-1]), float(bars.Low.iloc[-1])
    u, d, m = float(upper.iloc[-1]), float(lower.iloc[-1]), float(sma.iloc[-1])
    if np.isnan(u) or u <= d:
        return None

    touch_low, touch_up = l <= d, h >= u
    if touch_low and touch_up:                   # one huge bar through both bands -> use the close
        side = "LONG" if c < m else "SHORT"
    elif touch_low:
        side = "LONG"
    elif touch_up:
        side = "SHORT"
    else:
        return None

    tier = "Watch"
    if (c < d) if side == "LONG" else (c > u):   # closed outside the band
        width = ((upper - lower) / sma).dropna().values
        squeezed = width[-SQUEEZE_BARS:].min() <= np.percentile(width[-window:], SQUEEZE_PCTL)
        tier = "Squeeze+Fire" if squeezed else "Fire"
    return side, tier, (c - d) / (u - d)


def scan(data, tf):
    rule = RESAMPLE[tf]
    found = {s: {t: [] for t, _, _ in TIERS} for s in SIDES}   # side -> tier -> [(pct_b, ticker)]
    scanned = 0
    for t in TICKERS:
        df = get(data, yahoo(t))
        if df is None or len(df) < 60:
            continue
        bars = df if rule is None else df.resample(rule).agg(
            {"High": "max", "Low": "min", "Close": "last"}).dropna()
        if len(bars) < BB_LEN + SQUEEZE_BARS:
            continue
        scanned += 1
        sig = classify(bars, SQUEEZE_WINDOW[tf])
        if sig:
            side, tier, pct_b = sig
            found[side][tier].append((pct_b, t))

    # most stretched first: lowest %B for longs, highest %B for shorts
    for side, tiers in found.items():
        for tier, items in tiers.items():
            items.sort(reverse=(side == "SHORT"))
            tiers[tier] = [t for _, t in items]
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


def chunks(items, n=250):  # keeps each message under Discord's 2000-char limit
    for i in range(0, len(items), n):
        yield items[i:i + n]


def send_list(head, ts):
    for i, part in enumerate(chunks(ts)):
        post({"content": f"{head if i == 0 else ''}```{','.join(part)}```"})


def main():
    now = dt.datetime.now(TZ)
    data = download(TICKERS, "1d", "3y")   # one download serves every timeframe
    for tf in TIMEFRAMES:
        post({"content": f"**━━━━━━━━━━  {TF_ICON[tf]} {tf.upper()}  ━━━━━━━━━━**"})
        found, scanned = scan(data, tf)
        n = {s: sum(len(v) for v in found[s].values()) for s in SIDES}

        for side, (dot, color, explain) in SIDES.items():
            desc = (f"📅 {now:%d/%m/%Y %H:%M} IL\n"
                    f"סרקנו: **{scanned}** | 🟢 לונג: **{n['LONG']}** | 🔴 שורט: **{n['SHORT']}**\n"
                    "💎 Squeeze+Fire | 🔥 Fire (סגירה מחוץ) | 👀 Watch (נגיעה בלבד)\n" + explain)
            if not n[side]:
                desc += "\n\nאין סיגנלים."
            post({"embeds": [{
                "title": f"{dot} BB Reversion — {side.title()} [{tf}]",
                "description": desc,
                "color": color,
                "footer": {"text": "BB(20,2) · SMA20 target · StratNinja"},
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            }]})

            for tier, emoji, heading in TIERS:
                ts = found[side][tier]
                if ts:
                    send_list(f"{emoji} **{heading} {side} [{tf}]** · {len(ts)}\n", ts)


if __name__ == "__main__":
    main()
