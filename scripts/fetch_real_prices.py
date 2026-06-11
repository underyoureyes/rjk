"""
Fetch 2 years of real OHLCV data for the stock_market seed report.

Usage:
    python scripts/fetch_real_prices.py

Requires yfinance:
    pip install yfinance

Output:
    data/mock/daily_close_prices.json
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

TICKERS = ["PLTR", "GOOGL", "AAPL", "TSLA", "MSFT", "NVDA", "META"]
END   = datetime.now()
START = END - timedelta(days=730)

print(f"Fetching {len(TICKERS)} tickers from {START:%Y-%m-%d} to {END:%Y-%m-%d} ...")

rows = []
for ticker in TICKERS:
    print(f"  {ticker} ...", end=" ", flush=True)
    df = yf.download(ticker, start=START.strftime("%Y-%m-%d"),
                     end=END.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
    if df.empty:
        print("no data")
        continue

    # yfinance 0.2+ may return multi-level columns when downloading single ticker
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.droplevel(1)

    today_str = datetime.now().strftime("%Y-%m-%d")
    for date, row in df.iterrows():
        close_date = date.strftime("%Y-%m-%d")
        rows.append({
            "TICKER":      ticker,
            "CLOSE_DATE":  close_date,
            "MONTH":       date.replace(day=1).strftime("%Y-%m-%d"),
            "REPORT_DATE": today_str,
            "OPEN_PRICE":  round(float(row["Open"]),   2),
            "HIGH_PRICE":  round(float(row["High"]),   2),
            "LOW_PRICE":   round(float(row["Low"]),    2),
            "CLOSE_PRICE": round(float(row["Close"]),  2),
            "VOLUME":      int(row["Volume"]),
        })
    print(f"{len(df)} rows")

out = Path(__file__).parent.parent / "data" / "mock" / "daily_close_prices.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(f"\nWrote {len(rows):,} rows -> {out}")
