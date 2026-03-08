import yfinance as yf
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Test-YFinance")
symbols = ["DIA", "SPY", "QQQ"]
for symbol in symbols:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="7d", interval="30m")
    if df.empty:
        logger.error(f"No data returned for {symbol}")
    else:
        logger.info(f"Fetched {len(df)} records for {symbol}")
        print(f"\n{symbol} Data:\n", df.tail())