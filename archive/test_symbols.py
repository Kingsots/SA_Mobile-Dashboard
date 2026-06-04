import yfinance as yf
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Test-YFinance")
symbols = {
    "US30": "DIA",
    "XAUUSD": "GC=F",
    "USDJPY": "JPY=X",
    "GBPUSD": "GBPUSD=X",
    "EURJPY": "EURJPY=X",
    "AUDCAD": "AUDCAD=X"
}
for asset, symbol in symbols.items():
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="7d", interval="30m")
    if df.empty:
        logger.error(f"No data returned for {asset} ({symbol})")
    else:
        logger.info(f"Fetched {len(df)} records for {asset} ({symbol})")
        print(f"\n{asset} ({symbol}) Data:\n", df.tail())