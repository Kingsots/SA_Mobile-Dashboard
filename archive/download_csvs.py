import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Define symbols and their Yahoo Finance tickers
symbols = {
    "EURUSD": "EURUSD=X",
    "AUDUSD": "AUDUSD=X",
    "AUDJPY": "AUDJPY=X",
    "GBPJPY": "GBPJPY=X",
    "CADJPY": "CADJPY=X",
    "EURGBP": "EURGBP=X",
    "USDCAD": "USDCAD=X",
    "NAS100": "QQQ",
    "US500": "SPY"
}

# Set date range (60 days)
end_date = datetime.now()
start_date = end_date - timedelta(days=60)

# Download and save data for each symbol
for symbol, ticker in symbols.items():
    try:
        print(f"Fetching data for {symbol} ({ticker})...")
        df = yf.download(ticker, start=start_date, end=end_date, interval="1h")
        if not df.empty:
            df = df.reset_index().rename(columns={
                "Datetime": "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            csv_path = f"{symbol}_1h.csv"
            df.to_csv(csv_path, index=False)
            print(f"Saved {len(df)} records to {csv_path}")
        else:
            print(f"No data for {symbol}")
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")