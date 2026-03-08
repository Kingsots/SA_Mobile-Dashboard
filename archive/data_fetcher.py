import os
import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database path
DB_FILE = os.getenv("DB_FILE", "trading_bot.db")

# API keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

# --- Debugging: Confirm keys are loaded ---
print("🔑 API Key Check:")
print(f" ALPHA_VANTAGE_API_KEY: {'SET' if ALPHA_VANTAGE_API_KEY else 'MISSING'}")
print(f" FINNHUB_API_KEY: {'SET' if FINNHUB_API_KEY else 'MISSING'}")
print(f" POLYGON_API_KEY: {'SET' if POLYGON_API_KEY else 'MISSING'}")
print(f" TWELVE_DATA_API_KEY: {'SET' if TWELVE_DATA_API_KEY else 'MISSING'}")
print("==============================================")

# ---------------- Database ----------------
def init_db():
    """Initialize database and create ohlcv_data table if not exists."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            datetime TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL
        )
    """)
    conn.commit()
    conn.close()


def save_to_db(symbol, df):
    """Save OHLCV dataframe to SQLite database."""
    if df is None or df.empty:
        print(f"⚠️ No data to save for {symbol}")
        return

    conn = sqlite3.connect(DB_FILE)
    df["symbol"] = symbol
    df.to_sql("ohlcv_data", conn, if_exists="append", index=False)
    conn.close()
    print(f"💾 Saved {len(df)} rows for {symbol} into DB")


# ---------------- Fetchers ----------------
def fetch_from_alpha_vantage(symbol: str, interval="60min"):
    """Fetch OHLCV data from Alpha Vantage API."""
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "apikey": ALPHA_VANTAGE_API_KEY,
            "outputsize": "compact"
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        key = f"Time Series ({interval})"
        if key not in data:
            return None

        df = pd.DataFrame(data[key]).T
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index = pd.to_datetime(df.index)
        df = df.reset_index().rename(columns={"index": "datetime"})
        df = df.astype({
            "open": float, "high": float, "low": float,
            "close": float, "volume": float
        })
        return df

    except Exception as e:
        print(f"❌ Alpha Vantage fetch error for {symbol}: {e}")
        return None


def fetch_from_twelvedata(symbol: str, interval="1h"):
    """Fetch OHLCV data from TwelveData API."""
    try:
        url = f"https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "apikey": TWELVE_DATA_API_KEY,
            "outputsize": 5000
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if "values" not in data:
            return None

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.astype({
            "open": float, "high": float, "low": float,
            "close": float, "volume": float
        })
        return df

    except Exception as e:
        print(f"❌ TwelveData fetch error for {symbol}: {e}")
        return None


def fetch_from_polygon(symbol: str, multiplier=1, timespan="day", limit=30):
    """Fetch OHLCV data from Polygon.io API."""
    try:
        start_date = (datetime.today() - timedelta(days=limit)).strftime('%Y-%m-%d')
        end_date = datetime.today().strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": limit,
            "apiKey": POLYGON_API_KEY
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if "results" not in data:
            return None

        df = pd.DataFrame(data["results"])
        df.rename(columns={
            "t": "datetime",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
        return df

    except Exception as e:
        print(f"❌ Polygon fetch error for {symbol}: {e}")
        return None


def fetch_from_finnhub(symbol: str, resolution="60", count=500):
    """Fetch OHLCV data from Finnhub API."""
    try:
        import time
        now = int(time.time())
        frm = now - count * 3600

        url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": frm,
            "to": now,
            "token": FINNHUB_API_KEY
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if data.get("s") != "ok":
            return None

        df = pd.DataFrame({
            "datetime": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"]
        })
        return df

    except Exception as e:
        print(f"❌ Finnhub fetch error for {symbol}: {e}")
        return None


# ---------------- Unified Fetcher ----------------
class RobustMarketDataFetcher:
    """Unified fetcher with fallback across multiple APIs."""

    def __init__(self):
        self.sources = [
            fetch_from_twelvedata,
            fetch_from_alpha_vantage,
            fetch_from_finnhub,
            fetch_from_polygon
        ]

    def fetch_data(self, symbol: str, lookback_days: int = 60, interval: str = "1h"):
        """Try multiple APIs until one succeeds."""
        for fetcher in self.sources:
            try:
                if fetcher == fetch_from_polygon:
                    df = fetcher(symbol, timespan="day", limit=lookback_days)
                elif fetcher in [fetch_from_alpha_vantage, fetch_from_twelvedata]:
                    df = fetcher(symbol, interval)
                else:
                    df = fetcher(symbol)

                if df is not None and not df.empty:
                    df = df.dropna()
                    print(f"✅ {fetcher.__name__} succeeded for {symbol}, got {len(df)} rows")
                    return df
            except Exception as e:
                print(f"⚠️ {fetcher.__name__} failed for {symbol}: {e}")
        print(f"❌ All APIs failed for {symbol}")
        return None
