#!/usr/bin/env python3
"""StratNinja SMA20 + MFI - oversold / overbought stocks that already printed a
reversal bar -> Discord webhook.

Two conditions must hold together (money flow + price action):
  1. Money flow   - MFI(14) was oversold (<= 20) / overbought (>= 80) within the
                    last MFI_LOOKBACK daily bars.
  2. Price action - the last daily bar is a reversal bar:
        LONG : lower low than yesterday, green candle, closes above yesterday's close
        SHORT: higher high than yesterday, red candle, closes below yesterday's close
SMA20 is the target: LONG only while the price is below it, SHORT only while above it.

pip install yfinance pandas requests
1. Paste your webhook URL into WEBHOOK_URL below (keep it secret).
2. python sma20_mfi.py   (run after the US close, so the daily bar and its volume are final)
   Test without sending (Windows cmd):  set DRY_RUN=1  &&  python sma20_mfi.py
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
WEBHOOK_URL = "https://discord.com/api/webhooks/1570179649340702841/2i9qtgYJru1s_3r2JJ46A9yhoszVjgPwWNvyI49Vtmh-HoaC9svSbnuiEPa33h7kGvD-"
BOT_NAME = "StratNinja_SMA20_MFI"
MFI_LEN = 14
MFI_OVERSOLD, MFI_OVERBOUGHT = 20, 80
MFI_LOOKBACK = 3     # the extreme may be on the reversal bar or one of the 2 bars before it
SMA_LEN = 20
MAX_ROWS = 25        # rows shown in each embed (the copy-paste list has more)
try:
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # Windows without tzdata -> use the PC clock
    TZ = None

SIDES = {  # side -> (dot, embed colour, condition line, explanation line)
    "LONG": ("🟢", 0x57F287,
             f"💧 MFI({MFI_LEN}) ≤ {MFI_OVERSOLD} (מכירת יתר) + בר היפוך עולה: נמוך חדש, נר ירוק וסגירה מעל אתמול",
             "📈 **לונג** = מחיר מתחת SMA20 → Target: ריבאונד SMA20"),
    "SHORT": ("🔴", 0xED4245,
              f"💧 MFI({MFI_LEN}) ≥ {MFI_OVERBOUGHT} (קניית יתר) + בר היפוך יורד: גבוה חדש, נר אדום וסגירה מתחת לאתמול",
              "📉 **שורט** = מחיר מעל SMA20 → Target: ריבאונד SMA20"),
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
def mfi(df, n=MFI_LEN):
    """Money Flow Index: volume-weighted RSI on the typical price."""
    tp = (df.High + df.Low + df.Close) / 3
    flow = tp * df.Volume
    delta = tp.diff()
    pos = flow.where(delta > 0, 0.0).rolling(n).sum()
    neg = flow.where(delta < 0, 0.0).rolling(n).sum()
    return 100 - 100 / (1 + pos / neg)


def signal(df):
    """(side, price, MFI extreme, distance to SMA20 in %) for the last bar, or None."""
    if len(df) < SMA_LEN + MFI_LEN + 2:
        return None
    recent = mfi(df).iloc[-MFI_LOOKBACK:]
    if recent.isna().any():
        return None
    sma = float(df.Close.iloc[-SMA_LEN:].mean())
    cur, prev = df.iloc[-1], df.iloc[-2]
    price = float(cur.Close)
    dist = (sma / price - 1) * 100                       # + = SMA20 above price (long target)

    if (recent.min() <= MFI_OVERSOLD and cur.Low < prev.Low and cur.Close > cur.Open
            and cur.Close > prev.Close and price < sma):
        return "LONG", price, float(recent.min()), dist
    if (recent.max() >= MFI_OVERBOUGHT and cur.High > prev.High and cur.Close < cur.Open
            and cur.Close < prev.Close and price > sma):
        return "SHORT", price, float(recent.max()), dist
    return None


def scan():
    data = download(TICKERS, "1d", "1y")
    found, scanned = {"LONG": [], "SHORT": []}, 0
    for t in TICKERS:
        df = get(data, yahoo(t))
        if df is None or len(df) < 60:
            continue
        scanned += 1
        sig = signal(df)
        if sig:
            side, price, m, dist = sig
            found[side].append({"t": t, "price": price, "mfi": m, "dist": dist})
    found["LONG"].sort(key=lambda r: r["mfi"])           # most oversold first
    found["SHORT"].sort(key=lambda r: -r["mfi"])         # most overbought first
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


def main():
    found, scanned = scan()
    now = dt.datetime.now(TZ)
    nl, ns = len(found["LONG"]), len(found["SHORT"])

    for side, (dot, color, condition, explain) in SIDES.items():
        rows = found[side]
        desc = (f"📅 {now:%d/%m/%Y %H:%M} IL\n"
                f"סרקנו: **{scanned}** | 🟢 לונג: **{nl}** | 🔴 שורט: **{ns}**\n"
                f"{condition}\n{explain}")
        if rows:
            w = max(len(r["t"]) for r in rows)
            lines = [f"`{r['t']:<{w}}` ${r['price']:,.2f} | MFI {r['mfi']:.0f} | → SMA20 {r['dist']:+.1f}%"
                     for r in rows[:MAX_ROWS]]
            if len(rows) > MAX_ROWS:
                lines.append(f"… +{len(rows) - MAX_ROWS}")
            paste = ",".join(r["t"] for r in rows[:150])
            desc += f"\n\n**{side} · {len(rows)}**\n" + "\n".join(lines)
            desc += f"\n\n📋 **Tickers (copy-paste)**\n```{paste}```"
        else:
            desc += "\n\nאין סיגנלים."
        post({"embeds": [{
            "title": f"{dot} SMA20 + MFI — {side.title()} [Daily]",
            "description": desc,
            "color": color,
            "footer": {"text": f"MFI({MFI_LEN}) · SMA20 target · StratNinja"},
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }]})


if __name__ == "__main__":
    main()
