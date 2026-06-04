import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()
AV_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
TD_KEY = os.getenv("TWELVE_DATA_API_KEY")

# Pairs and their mappings
symbols = {
    "EURUSD": {"av": ("EUR", "USD"), "td": "EUR/USD"},
    "AUDUSD": {"av": ("AUD", "USD"), "td": "AUD/USD"},
    "AUDJPY": {"av": ("AUD", "JPY"), "td": "AUD/JPY"},
    "GBPJPY": {"av": ("GBP", "JPY"), "td": "GBP/JPY"},
    "CADJPY": {"av": ("CAD", "JPY"), "td": "CAD/JPY"},
    "EURGBP": {"av": ("EUR", "GBP"), "td": "EUR/GBP"},
    "USDCAD": {"av": ("USD", "CAD"), "td": "USD/CAD"},
    "NAS100": {"av": None, "td": "NDX"},   # Nasdaq 100
    "US500": {"av": None, "td": "SPX"},    # S&P 500
}

# Base URLs
AV_URL = "https://www.alphavantage.co/query"
TD_URL = "https://api.twelvedata.com/time_series"

def fetch_from_alpha_vantage(pair, mapping, filename):
    """Try fetching from Alpha Vantage"""
    if mapping is None:
        return None  # not supported
    
    from_symbol, to_symbol = mapping
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "interval": "60min",
        "outputsize": "full",
        "apikey": AV_KEY,
    }
    print(f"📥 Trying Alpha Vantage for {pair} ...")
    r = requests.get(AV_URL, params=params)
    data = r.json()
    
    key = "Time Series FX (60min)"
    if key not in data:
        print(f"⚠️ Alpha Vantage failed for {pair}: {data}")
        return None

    df = pd.DataFrame.from_dict(data[key], orient="index")
    df = df.rename(columns=lambda x: x.split(". ")[1])
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.to_csv(filename)
    print(f"✅ Saved {filename} via Alpha Vantage ({len(df)} rows)")
    return df

def fetch_from_twelvedata(pair, symbol, filename):
    """Fallback: Fetch from Twelve Data"""
    params = {
        "symbol": symbol,
        "interval": "1h",
        "outputsize": 5000,
        "apikey": TD_KEY,
    }
    print(f"🔄 Falling back to Twelve Data for {pair} ...")
    r = requests.get(TD_URL, params=params)
    data = r.json()
    
    if "values" not in data:
        print(f"❌ Twelve Data also failed for {pair}: {data}")
        return None
    
    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.rename(columns={"datetime": "date"})
    df = df.sort_values("date")
    df.to_csv(filename, index=False)
    print(f"✅ Saved {filename} via Twelve Data ({len(df)} rows)")
    return df

def main():
    for pair, mapping in symbols.items():
        filename = f"{pair}_1h.csv"
        success = False

        # Try Alpha Vantage first
        df = fetch_from_alpha_vantage(pair, mapping["av"], filename)
        if df is not None:
            success = True
        else:
            # Sleep before fallback to avoid instant API spam
            time.sleep(2)
            df = fetch_from_twelvedata(pair, mapping["td"], filename)
            if df is not None:
                success = True

        if not success:
            print(f"⚠️ Could not fetch {pair} from either source.")

        # Respect Alpha Vantage rate limit: 5 calls per minute
        time.sleep(15)

if __name__ == "__main__":
    main()
